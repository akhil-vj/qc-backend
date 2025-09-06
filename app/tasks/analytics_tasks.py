"""Complete analytics background tasks"""

from celery.utils.log import get_task_logger
from datetime import datetime, timedelta, date
import asyncio

from app.core.celery_app import celery_app
from app.core.database import get_db_sync
from app.services.analytics import AnalyticsService

logger = get_task_logger(__name__)

@celery_app.task(name="calculate_product_trending_scores")
def calculate_product_trending_scores():
    """Calculate trending scores for all products"""
    try:
        db = next(get_db_sync())
        
        # Calculate trending score based on:
        # - Recent views (last 7 days)
        # - Recent purchases (last 7 days)
        # - Review ratings
        # - Time decay factor
        
        query = """
        UPDATE products p
        SET trending_score = subquery.score
        FROM (
            SELECT 
                p.id,
                (
                    -- Recent views score (normalized 0-30)
                    LEAST(30, 
                        COALESCE((
                            SELECT COUNT(*) * 0.1
                            FROM product_views pv
                            WHERE pv.product_id = p.id
                            AND pv.created_at >= NOW() - INTERVAL '7 days'
                        ), 0)
                    ) +
                    -- Recent purchases score (normalized 0-40)
                    LEAST(40,
                        COALESCE((
                            SELECT SUM(oi.quantity) * 2
                            FROM order_items oi
                            JOIN orders o ON oi.order_id = o.id
                            WHERE oi.product_id = p.id
                            AND o.created_at >= NOW() - INTERVAL '7 days'
                            AND o.status IN ('confirmed', 'shipped', 'delivered')
                        ), 0)
                    ) +
                    -- Rating score (0-20)
                    COALESCE(p.rating * 4, 0) +
                    -- Recency bonus (0-10)
                    CASE 
                        WHEN p.created_at >= NOW() - INTERVAL '7 days' THEN 10
                        WHEN p.created_at >= NOW() - INTERVAL '30 days' THEN 5
                        ELSE 0
                    END
                ) as score
            FROM products p
            WHERE p.status = 'active'
        ) subquery
        WHERE p.id = subquery.id
        """
        
        db.execute(query)
        db.commit()
        
        logger.info("Updated trending scores for all products")
        
        # Cache top trending products
        from app.core.cache import cache
        
        top_trending = db.execute("""
            SELECT id, title, primary_image, price, rating, trending_score
            FROM products
            WHERE status = 'active'
            ORDER BY trending_score DESC
            LIMIT 20
        """).fetchall()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        trending_data = [
            {
                "id": str(p.id),
                "title": p.title,
                "image": p.primary_image,
                "price": float(p.price),
                "rating": float(p.rating) if p.rating else None,
                "score": float(p.trending_score)
            }
            for p in top_trending
        ]
        
        loop.run_until_complete(
            cache.set("trending_products", trending_data, expire=3600)
        )
        
        loop.close()
        
        return {"status": "success", "products_updated": len(trending_data)}
        
    except Exception as e:
        logger.error(f"Error calculating trending scores: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="generate_seller_performance_report")
def generate_seller_performance_report(seller_id: str, period: str = "monthly"):
    """Generate seller performance report"""
    try:
        db = next(get_db_sync())
        
        # Determine date range
        if period == "weekly":
            start_date = date.today() - timedelta(days=7)
        elif period == "monthly":
            start_date = date.today().replace(day=1)
        else:
            start_date = date.today() - timedelta(days=30)
            
        end_date = date.today()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        analytics_service = AnalyticsService(db)
        # Generate comprehensive seller report
        report_data = loop.run_until_complete(
            analytics_service._get_seller_dashboard_metrics(
                seller_id=seller_id,
                date_range=(start_date, end_date)
            )
        )
        
        # Add additional analytics
        additional_metrics = db.execute("""
            WITH product_performance AS (
                SELECT 
                    p.id,
                    p.title,
                    COUNT(DISTINCT pv.user_id) as unique_views,
                    COUNT(pv.id) as total_views,
                    COALESCE(SUM(oi.quantity), 0) as units_sold,
                    COALESCE(SUM(oi.quantity * oi.price), 0) as revenue,
                    COUNT(DISTINCT r.id) as review_count,
                    AVG(r.rating) as avg_rating
                FROM products p
                LEFT JOIN product_views pv ON p.id = pv.product_id 
                    AND pv.created_at BETWEEN :start_date AND :end_date
                LEFT JOIN order_items oi ON p.id = oi.product_id
                LEFT JOIN orders o ON oi.order_id = o.id 
                    AND o.created_at BETWEEN :start_date AND :end_date
                    AND o.status IN ('confirmed', 'shipped', 'delivered')
                LEFT JOIN reviews r ON p.id = r.product_id
                    AND r.created_at BETWEEN :start_date AND :end_date
                WHERE p.seller_id = :seller_id
                GROUP BY p.id, p.title
            ),
            customer_retention AS (
                SELECT 
                    COUNT(DISTINCT CASE WHEN order_count = 1 THEN buyer_id END) as one_time_buyers,
                    COUNT(DISTINCT CASE WHEN order_count > 1 THEN buyer_id END) as repeat_buyers,
                    AVG(order_count) as avg_orders_per_customer
                FROM (
                    SELECT buyer_id, COUNT(*) as order_count
                    FROM orders
                    WHERE seller_id = :seller_id
                    AND created_at BETWEEN :start_date AND :end_date
                    AND status IN ('confirmed', 'shipped', 'delivered')
                    GROUP BY buyer_id
                ) buyer_orders
            )
            SELECT 
                (SELECT json_agg(pp.*) FROM product_performance pp) as product_metrics,
                (SELECT row_to_json(cr.*) FROM customer_retention cr) as retention_metrics
        """, {
            "seller_id": seller_id,
            "start_date": start_date,
            "end_date": end_date
        }).fetchone()
        
        report_data["product_performance"] = additional_metrics.product_metrics or []
        report_data["customer_retention"] = additional_metrics.retention_metrics or {}
        
        # Store report
        from app.models.analytics import SellerReport
        
        report = SellerReport(
            seller_id=seller_id,
            report_type=period,
            period_start=start_date,
            period_end=end_date,
            data=report_data,
            generated_at=datetime.utcnow()
        )
        
        db.add(report)
        db.commit()
        
        loop.close()
        
        # Send report notification
        from app.tasks.email_tasks import send_email_task
        seller = db.query(User).filter(User.id == seller_id).first()
        
        if seller and seller.email:
            send_email_task.delay(
                to_email=seller.email,
                subject=f"Your {period.capitalize()} Performance Report",
                body="Your performance report is ready.",
                html_body=f"<p>View your detailed report <a href='{settings.FRONTEND_URL}/seller/reports/{report.id}'>here</a></p>"
            )
            
        logger.info(f"Generated {period} report for seller {seller_id}")
        
        return {
            "report_id": str(report.id),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error generating seller report: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="calculate_user_segments")
def calculate_user_segments():
    """Calculate and update user segments for targeted marketing"""
    try:
        db = next(get_db_sync())
        
        # Define segments
        segments_query = """
        WITH user_metrics AS (
            SELECT 
                u.id,
                COUNT(DISTINCT o.id) as order_count,
                COALESCE(SUM(o.total_amount), 0) as lifetime_value,
                MAX(o.created_at) as last_order_date,
                AVG(o.total_amount) as avg_order_value,
                u.created_at as registration_date
            FROM users u
            LEFT JOIN orders o ON u.id = o.buyer_id
                AND o.status IN ('confirmed', 'shipped', 'delivered')
            WHERE u.role = 'buyer'
            GROUP BY u.id, u.created_at
        )
        UPDATE users u
        SET segment = 
            CASE 
                -- VIP customers (high value, frequent)
                WHEN um.lifetime_value > 10000 AND um.order_count > 10 THEN 'vip'
                
                -- Regular customers (medium activity)
                WHEN um.order_count >= 3 AND um.last_order_date > NOW() - INTERVAL '90 days' THEN 'regular'
                
                -- At risk (was active but not recently)
                WHEN um.order_count > 0 AND um.last_order_date < NOW() - INTERVAL '90 days' THEN 'at_risk'
                
                -- New customers (recent registration or first purchase)
                WHEN um.order_count <= 1 AND u.created_at > NOW() - INTERVAL '30 days' THEN 'new'
                
                -- Dormant (registered but never purchased)
                WHEN um.order_count = 0 AND u.created_at < NOW() - INTERVAL '30 days' THEN 'dormant'
                
                ELSE 'prospect'
            END,
            segment_updated_at = NOW()
        FROM user_metrics um
        WHERE u.id = um.id
        """
        
        result = db.execute(segments_query)
        users_updated = result.rowcount
        
        # Get segment counts
        segment_counts = db.execute("""
            SELECT segment, COUNT(*) as count
            FROM users
            WHERE role = 'buyer'
            GROUP BY segment
        """).fetchall()
        
        db.commit()
        
        logger.info(f"Updated segments for {users_updated} users")
        
        return {
            "users_updated": users_updated,
            "segment_distribution": {
                row.segment: row.count for row in segment_counts
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating user segments: {str(e)}")
        raise
    finally:
        db.close()



# """Analytics-related Celery tasks"""

# from celery.utils.log import get_task_logger
# from datetime import datetime, timedelta
# import asyncio

# from app.core.celery_app import celery_app
# from app.core.database import get_db_sync

# logger = get_task_logger(__name__)

# @celery_app.task(name="generate_daily_analytics")
# def generate_daily_analytics():
#     """Generate daily analytics snapshots"""
#     try:
#         db = next(get_db_sync())
        
#         from app.services.analytics import AnalyticsService
#         service = AnalyticsService(db)
        
#         # Generate analytics for yesterday
#         yesterday = datetime.utcnow().date() - timedelta(days=1)
        
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
        
#         # Generate various analytics
#         tasks = [
#             service.generate_sales_report(yesterday),
#             service.generate_user_activity_report(yesterday),
#             service.generate_product_performance_report(yesterday),
#             service.generate_seller_analytics(yesterday)
#         ]
        
#         results = loop.run_until_complete(asyncio.gather(*tasks))
#         loop.close()
        
#         logger.info(f"Generated daily analytics for {yesterday}")
        
#         return {
#             "date": yesterday.isoformat(),
#             "reports_generated": len(results)
#         }
        
#     except Exception as e:
#         logger.error(f"Error generating daily analytics: {str(e)}")
#         raise
#     finally:
#         db.close()

# @celery_app.task(name="calculate_trending_products")
# def calculate_trending_products():
#     """Calculate trending products based on recent activity"""
#     try:
#         db = next(get_db_sync())
        
#         # Calculate trending scores
#         query = """
#         UPDATE products
#         SET trending_score = (
#             (view_count * 0.3) +
#             (purchase_count * 0.5) +
#             (COALESCE(rating, 0) * 0.2) +
#             (CASE 
#                 WHEN created_at > NOW() - INTERVAL '7 days' THEN 10
#                 WHEN created_at > NOW() - INTERVAL '30 days' THEN 5
#                 ELSE 0
#             END)
#         )
#         WHERE status = 'active'
#         """
        
#         db.execute(query)
#         db.commit()
        
#         logger.info("Updated trending scores for all products")
        
#         return {"status": "success"}
        
#     except Exception as e:
#         logger.error(f"Error calculating trending products: {str(e)}")
#         raise
#     finally:
#         db.close()

# @celery_app.task(name="generate_seller_monthly_report")
# def generate_seller_monthly_report(seller_id: str):
#     """Generate monthly report for a seller"""
#     try:
#         db = next(get_db_sync())
        
#         from app.services.reports import ReportService
#         service = ReportService(db)
        
#         # Generate report for last month
#         last_month = datetime.utcnow().date().replace(day=1) - timedelta(days=1)
        
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
        
#         report = loop.run_until_complete(
#             service.generate_seller_monthly_report(seller_id, last_month)
#         )
        
#         loop.close()
        
#         # Send report via email
#         from app.tasks.email_tasks import send_email_task
#         send_email_task.delay(
#             to_email=report["seller_email"],
#             subject=f"Your Monthly Report - {last_month.strftime('%B %Y')}",
#             body="Please find your monthly report attached.",
#             html_body=report["html_content"],
#             attachments=[{
#                 "filename": f"report_{last_month.strftime('%Y_%m')}.pdf",
#                 "content": report["pdf_content"],
#                 "type": "application/pdf"
#             }]
#         )
        
#         logger.info(f"Generated monthly report for seller {seller_id}")
        
#         return {"status": "success", "month": last_month.isoformat()}
        
#     except Exception as e:
#         logger.error(f"Error generating seller report: {str(e)}")
#         raise
#     finally:
#         db.close()
