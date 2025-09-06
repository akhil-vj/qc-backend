"""Price tracking and alert tasks"""

from celery.utils.log import get_task_logger
from datetime import datetime, timedelta
import asyncio

from app.core.celery_app import celery_app
from app.core.database import get_db_sync
from app.services.price_tracking import PriceTrackingService

logger = get_task_logger(__name__)

@celery_app.task(name="check_price_alerts")
def check_price_alerts():
    """Check and trigger price alerts"""
    try:
        db = next(get_db_sync())
        
        # Get active price alerts
        from app.models.price_alert import PriceAlert, PriceAlertStatus
        from app.models.product import Product
        
        alerts = db.query(PriceAlert).join(Product).filter(
            PriceAlert.status == PriceAlertStatus.ACTIVE
        ).all()
        
        triggered_count = 0
        
        for alert in alerts:
            product = alert.product
            triggered = False
            
            # Check alert conditions
            if alert.alert_type == "drop_below" and product.price <= alert.target_price:
                triggered = True
            elif alert.alert_type == "rise_above" and product.price >= alert.target_price:
                triggered = True
            elif alert.alert_type == "any_change":
                price_change = abs(product.price - alert.current_price)
                if price_change / alert.current_price >= 0.05:  # 5% change
                    triggered = True
                    
            if triggered:
                # Update alert
                alert.status = PriceAlertStatus.TRIGGERED
                alert.triggered_at = datetime.utcnow()
                alert.triggered_price = product.price
                
                # Send notification
                from app.tasks.push_notification_tasks import send_push_notification_task
                
                if alert.alert_type == "drop_below":
                    title = "Price Drop Alert! 📉"
                    message = f"{product.title} is now ₹{product.price} (target: ₹{alert.target_price})"
                else:
                    title = "Price Alert! 🔔"
                    message = f"{product.title} price changed to ₹{product.price}"
                    
                send_push_notification_task.delay(
                    user_id=str(alert.user_id),
                    title=title,
                    body=message,
                    data={
                        "type": "price_alert",
                        "product_id": str(product.id),
                        "alert_id": str(alert.id)
                    },
                    priority="high"
                )
                
                triggered_count += 1
                
        db.commit()
        
        logger.info(f"Triggered {triggered_count} price alerts")
        
        return {"alerts_triggered": triggered_count}
        
    except Exception as e:
        logger.error(f"Error checking price alerts: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="update_price_history")
def update_price_history():
    """Track price changes for all products"""
    try:
        db = next(get_db_sync())
        
        # Get products with recent price changes
        query = """
        INSERT INTO price_history (product_id, old_price, new_price, change_percentage, change_reason)
        SELECT 
            p.id,
            ph.new_price,
            p.price,
            CASE 
                WHEN ph.new_price > 0 
                THEN ((p.price - ph.new_price) / ph.new_price) * 100
                ELSE 0
            END,
            'Daily price tracking'
        FROM products p
        LEFT JOIN LATERAL (
            SELECT new_price
            FROM price_history
            WHERE product_id = p.id
            ORDER BY created_at DESC
            LIMIT 1
        ) ph ON TRUE
        WHERE p.status = 'active'
        AND (ph.new_price IS NULL OR ph.new_price != p.price)
        """
        
        result = db.execute(query)
        changes_tracked = result.rowcount
        
        db.commit()
        
        logger.info(f"Tracked {changes_tracked} price changes")
        
        return {"changes_tracked": changes_tracked}
        
    except Exception as e:
        logger.error(f"Error updating price history: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="generate_price_insights")
def generate_price_insights():
    """Generate pricing insights and recommendations"""
    try:
        db = next(get_db_sync())
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from app.services.price_tracking import PriceTrackingService
        service = PriceTrackingService(db)
        
        # Get categories with significant price changes
        insights_query = """
        WITH category_trends AS (
            SELECT 
                c.id as category_id,
                c.name as category_name,
                AVG(ph.change_percentage) as avg_price_change,
                COUNT(DISTINCT ph.product_id) as products_changed,
                SUM(CASE WHEN ph.change_percentage < -5 THEN 1 ELSE 0 END) as products_decreased,
                SUM(CASE WHEN ph.change_percentage > 5 THEN 1 ELSE 0 END) as products_increased
            FROM categories c
            JOIN products p ON c.id = p.category_id
            JOIN price_history ph ON p.id = ph.product_id
            WHERE ph.created_at >= NOW() - INTERVAL '7 days'
            GROUP BY c.id, c.name
            HAVING COUNT(DISTINCT ph.product_id) > 5
        )
        SELECT * FROM category_trends
        ORDER BY ABS(avg_price_change) DESC
        LIMIT 10
        """
        
        category_trends = db.execute(insights_query).fetchall()
        
        # Generate insights
        insights = []
        
        for trend in category_trends:
            if trend.avg_price_change < -5:
                insight = {
                    "type": "price_drop",
                    "category": trend.category_name,
                    "message": f"Prices in {trend.category_name} dropped by {abs(trend.avg_price_change):.1f}% this week",
                    "affected_products": trend.products_decreased
                }
            elif trend.avg_price_change > 5:
                insight = {
                    "type": "price_rise",
                    "category": trend.category_name,
                    "message": f"Prices in {trend.category_name} increased by {trend.avg_price_change:.1f}% this week",
                    "affected_products": trend.products_increased
                }
            else:
                continue
                
            insights.append(insight)
            
        # Store insights
        from app.models.analytics import PriceInsight
        
        for insight in insights:
            db_insight = PriceInsight(
                insight_type=insight["type"],
                category=insight["category"],
                data=insight,
                created_at=datetime.utcnow()
            )
            db.add(db_insight)
            
        db.commit()
        
        loop.close()
        
        logger.info(f"Generated {len(insights)} price insights")
        
        return {
            "insights_generated": len(insights),
            "insights": insights
        }
        
    except Exception as e:
        logger.error(f"Error generating price insights: {str(e)}")
        raise
    finally:
        db.close()
