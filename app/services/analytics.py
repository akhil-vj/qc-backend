"""Complete analytics service with data aggregation and reporting"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, distinct, case, text
from decimal import Decimal
import logging
import json
from collections import defaultdict

from app.models.order import Order, OrderItem
from app.models.user import User
from app.models.product import Product
from app.models.analytics import UserActivity, ProductView, AnalyticsEvent
from app.models.referral import ReferralTracking

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Complete analytics service for data aggregation and reporting"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_dashboard_metrics(
        self,
        user_id: Optional[str] = None,
        user_role: str = "admin",
        date_range: Optional[Tuple[date, date]] = None
    ) -> Dict[str, Any]:
        """Get comprehensive dashboard metrics"""
        if not date_range:
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            date_range = (start_date, end_date)
            
        if user_role == "admin":
            return await self._get_admin_dashboard_metrics(date_range)
        elif user_role == "seller":
            return await self._get_seller_dashboard_metrics(user_id, date_range)
        else:
            return await self._get_user_dashboard_metrics(user_id, date_range)
            
    async def _get_admin_dashboard_metrics(
        self,
        date_range: Tuple[date, date]
    ) -> Dict[str, Any]:
        """Get admin dashboard metrics"""
        start_date, end_date = date_range
        
        # Overview metrics
        overview_query = """
        WITH date_range AS (
            SELECT :start_date::date as start_date, :end_date::date as end_date
        ),
        current_period AS (
            SELECT 
                COUNT(DISTINCT o.id) as total_orders,
                COALESCE(SUM(o.total_amount), 0) as total_revenue,
                COUNT(DISTINCT o.buyer_id) as unique_customers,
                COALESCE(AVG(o.total_amount), 0) as avg_order_value
            FROM orders o, date_range dr
            WHERE o.created_at >= dr.start_date
            AND o.created_at < dr.end_date + INTERVAL '1 day'
            AND o.status IN ('confirmed', 'shipped', 'delivered')
        ),
        previous_period AS (
            SELECT 
                COUNT(DISTINCT o.id) as total_orders,
                COALESCE(SUM(o.total_amount), 0) as total_revenue
            FROM orders o, date_range dr
            WHERE o.created_at >= dr.start_date - (dr.end_date - dr.start_date + 1)
            AND o.created_at < dr.start_date
            AND o.status IN ('confirmed', 'shipped', 'delivered')
        ),
        user_metrics AS (
            SELECT 
                COUNT(DISTINCT CASE WHEN u.created_at >= dr.start_date THEN u.id END) as new_users,
                COUNT(DISTINCT CASE WHEN u.role = 'seller' AND u.created_at >= dr.start_date THEN u.id END) as new_sellers
            FROM users u, date_range dr
        )
        SELECT 
            cp.total_orders,
            cp.total_revenue,
            cp.unique_customers,
            cp.avg_order_value,
            CASE 
                WHEN pp.total_orders > 0 
                THEN ROUND(100.0 * (cp.total_orders - pp.total_orders) / pp.total_orders, 2)
                ELSE 0
            END as order_growth,
            CASE 
                WHEN pp.total_revenue > 0 
                THEN ROUND(100.0 * (cp.total_revenue - pp.total_revenue) / pp.total_revenue, 2)
                ELSE 0
            END as revenue_growth,
            um.new_users,
            um.new_sellers
        FROM current_period cp, previous_period pp, user_metrics um
        """
        
        overview = await self.db.execute(
            text(overview_query),
            {"start_date": start_date, "end_date": end_date}
        )
        overview = overview.fetchone()._asdict()
        
        # Daily breakdown
        daily_query = """
        SELECT 
            DATE(o.created_at) as date,
            COUNT(DISTINCT o.id) as orders,
            COALESCE(SUM(o.total_amount), 0) as revenue,
            COUNT(DISTINCT o.buyer_id) as customers
        FROM orders o
        WHERE o.created_at >= :start_date
        AND o.created_at < :end_date + INTERVAL '1 day'
        AND o.status IN ('confirmed', 'shipped', 'delivered')
        GROUP BY DATE(o.created_at)
        ORDER BY date
        """
        
        daily_data = await self.db.execute(
            text(daily_query),
            {"start_date": start_date, "end_date": end_date}
        )
        
        # Category performance
        category_query = """
        SELECT 
            c.name as category,
            COUNT(DISTINCT oi.order_id) as orders,
            SUM(oi.quantity) as units_sold,
            SUM(oi.quantity * oi.price) as revenue
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        JOIN orders o ON oi.order_id = o.id
        WHERE o.created_at >= :start_date
        AND o.created_at < :end_date + INTERVAL '1 day'
        AND o.status IN ('confirmed', 'shipped', 'delivered')
        GROUP BY c.id, c.name
        ORDER BY revenue DESC
        LIMIT 10
        """
        
        categories = await self.db.execute(
            text(category_query),
            {"start_date": start_date, "end_date": end_date}
        )
        
        # Top products
        products_query = """
        SELECT 
            p.id,
            p.title,
            p.primary_image,
            COUNT(DISTINCT oi.order_id) as order_count,
            SUM(oi.quantity) as units_sold,
            SUM(oi.quantity * oi.price) as revenue
        FROM products p
        JOIN order_items oi ON p.id = oi.product_id
        JOIN orders o ON oi.order_id = o.id
        WHERE o.created_at >= :start_date
        AND o.created_at < :end_date + INTERVAL '1 day'
        AND o.status IN ('confirmed', 'shipped', 'delivered')
        GROUP BY p.id, p.title, p.primary_image
        ORDER BY revenue DESC
        LIMIT 10
        """
        
        top_products = await self.db.execute(
            text(products_query),
            {"start_date": start_date, "end_date": end_date}
        )
        
        # User engagement
        engagement_query = """
        WITH user_sessions AS (
            SELECT 
                DATE(created_at) as date,
                COUNT(DISTINCT user_id) as active_users,
                COUNT(DISTINCT session_id) as sessions,
                AVG(CASE WHEN activity_type = 'page_view' THEN 1 ELSE 0 END) as pages_per_session
            FROM user_activities
            WHERE created_at >= :start_date
            AND created_at < :end_date + INTERVAL '1 day'
            GROUP BY DATE(created_at)
        ),
        conversion_funnel AS (
            SELECT 
                COUNT(DISTINCT CASE WHEN activity_type = 'view_product' THEN user_id END) as viewed_products,
                COUNT(DISTINCT CASE WHEN activity_type = 'add_to_cart' THEN user_id END) as added_to_cart,
                COUNT(DISTINCT CASE WHEN activity_type = 'checkout_started' THEN user_id END) as started_checkout,
                COUNT(DISTINCT CASE WHEN activity_type = 'order_completed' THEN user_id END) as completed_order
            FROM user_activities
            WHERE created_at >= :start_date
            AND created_at < :end_date + INTERVAL '1 day'
        )
        SELECT 
            COALESCE(AVG(us.active_users), 0) as avg_daily_active_users,
            COALESCE(SUM(us.sessions), 0) as total_sessions,
            cf.viewed_products,
            cf.added_to_cart,
            cf.started_checkout,
            cf.completed_order,
            CASE 
                WHEN cf.viewed_products > 0 
                THEN ROUND(100.0 * cf.completed_order / cf.viewed_products, 2)
                ELSE 0
            END as conversion_rate
        FROM user_sessions us, conversion_funnel cf
        GROUP BY cf.viewed_products, cf.added_to_cart, cf.started_checkout, cf.completed_order
        """
        
        engagement = await self.db.execute(
            text(engagement_query),
            {"start_date": start_date, "end_date": end_date}
        )
        engagement = engagement.fetchone()
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "overview": {
                "total_orders": overview["total_orders"],
                "total_revenue": float(overview["total_revenue"]),
                "unique_customers": overview["unique_customers"],
                "avg_order_value": float(overview["avg_order_value"]),
                "order_growth": float(overview["order_growth"]),
                "revenue_growth": float(overview["revenue_growth"]),
                "new_users": overview["new_users"],
                "new_sellers": overview["new_sellers"]
            },
            "daily_breakdown": [
                {
                    "date": row.date.isoformat(),
                    "orders": row.orders,
                    "revenue": float(row.revenue),
                    "customers": row.customers
                }
                for row in daily_data
            ],
            "category_performance": [
                {
                    "category": row.category,
                    "orders": row.orders,
                    "units_sold": row.units_sold,
                    "revenue": float(row.revenue)
                }
                for row in categories
            ],
            "top_products": [
                {
                    "id": str(row.id),
                    "title": row.title,
                    "image": row.primary_image,
                    "order_count": row.order_count,
                    "units_sold": row.units_sold,
                    "revenue": float(row.revenue)
                }
                for row in top_products
            ],
            "user_engagement": {
                "avg_daily_active_users": int(engagement.avg_daily_active_users) if engagement else 0,
                "total_sessions": engagement.total_sessions if engagement else 0,
                "conversion_funnel": {
                    "viewed_products": engagement.viewed_products if engagement else 0,
                    "added_to_cart": engagement.added_to_cart if engagement else 0,
                    "started_checkout": engagement.started_checkout if engagement else 0,
                    "completed_order": engagement.completed_order if engagement else 0
                },
                "conversion_rate": float(engagement.conversion_rate) if engagement else 0
            }
        }
        
    async def _get_seller_dashboard_metrics(
        self,
        seller_id: str,
        date_range: Tuple[date, date]
    ) -> Dict[str, Any]:
        """Get seller-specific dashboard metrics"""
        start_date, end_date = date_range
        
        # Overview metrics
        overview_query = """
        WITH current_stats AS (
            SELECT 
                COUNT(DISTINCT o.id) as total_orders,
                COALESCE(SUM(o.total_amount), 0) as total_revenue,
                COUNT(DISTINCT o.buyer_id) as unique_customers,
                COALESCE(AVG(o.total_amount), 0) as avg_order_value,
                COUNT(DISTINCT CASE WHEN o.status = 'pending' THEN o.id END) as pending_orders,
                COUNT(DISTINCT CASE WHEN o.status = 'delivered' THEN o.id END) as delivered_orders
            FROM orders o
            WHERE o.seller_id = :seller_id
            AND o.created_at >= :start_date
            AND o.created_at < :end_date + INTERVAL '1 day'
        ),
        product_stats AS (
            SELECT 
                COUNT(DISTINCT p.id) as total_products,
                COUNT(DISTINCT CASE WHEN p.status = 'active' THEN p.id END) as active_products,
                COUNT(DISTINCT CASE WHEN p.stock < 10 THEN p.id END) as low_stock_products,
                COALESCE(AVG(p.rating), 0) as avg_product_rating
            FROM products p
            WHERE p.seller_id = :seller_id
        )
        SELECT * FROM current_stats, product_stats
        """
        
        overview = await self.db.execute(
            text(overview_query),
            {"seller_id": seller_id, "start_date": start_date, "end_date": end_date}
        )
        overview = overview.fetchone()._asdict()
        
        # Daily sales
        daily_sales = await self._get_daily_sales(seller_id, start_date, end_date)
        
        # Top products
        top_products = await self._get_top_products(seller_id, start_date, end_date, limit=10)
        
        # Customer analytics
        customer_analytics = await self._get_customer_analytics(seller_id, start_date, end_date)
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "overview": {
                "total_orders": overview["total_orders"],
                "total_revenue": float(overview["total_revenue"]),
                "unique_customers": overview["unique_customers"],
                "avg_order_value": float(overview["avg_order_value"]),
                "pending_orders": overview["pending_orders"],
                "delivered_orders": overview["delivered_orders"],
                "total_products": overview["total_products"],
                "active_products": overview["active_products"],
                "low_stock_products": overview["low_stock_products"],
                "avg_product_rating": float(overview["avg_product_rating"])
            },
            "daily_sales": daily_sales,
            "top_products": top_products,
            "customer_analytics": customer_analytics
        }
        
    async def generate_sales_report(
        self,
        start_date: date,
        end_date: date,
        group_by: str = "day",
        seller_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate detailed sales report"""
        # Date truncation based on grouping
        date_trunc = {
            "hour": "hour",
            "day": "day",
            "week": "week",
            "month": "month",
            "quarter": "quarter",
            "year": "year"
        }.get(group_by, "day")
        
        query = f"""
        SELECT 
            DATE_TRUNC('{date_trunc}', o.created_at) as period,
            COUNT(DISTINCT o.id) as order_count,
            COUNT(DISTINCT o.buyer_id) as unique_customers,
            SUM(o.subtotal) as gross_revenue,
            SUM(o.discount_amount) as total_discount,
            SUM(o.delivery_fee) as delivery_revenue,
            SUM(o.total_amount) as net_revenue,
            AVG(o.total_amount) as avg_order_value,
            COUNT(DISTINCT CASE WHEN o.payment_method = 'cod' THEN o.id END) as cod_orders,
            COUNT(DISTINCT CASE WHEN o.payment_method != 'cod' THEN o.id END) as prepaid_orders
        FROM orders o
        WHERE o.created_at >= :start_date
        AND o.created_at < :end_date + INTERVAL '1 day'
        AND o.status IN ('confirmed', 'shipped', 'delivered')
        """
        
        params = {"start_date": start_date, "end_date": end_date}
        
        if seller_id:
            query += " AND o.seller_id = :seller_id"
            params["seller_id"] = seller_id
            
        query += f" GROUP BY DATE_TRUNC('{date_trunc}', o.created_at) ORDER BY period"
        
        result = await self.db.execute(text(query), params)
        
        sales_data = []
        total_stats = defaultdict(lambda: 0)
        
        for row in result:
            period_data = {
                "period": row.period.isoformat(),
                "order_count": row.order_count,
                "unique_customers": row.unique_customers,
                "gross_revenue": float(row.gross_revenue),
                "total_discount": float(row.total_discount),
                "delivery_revenue": float(row.delivery_revenue),
                "net_revenue": float(row.net_revenue),
                "avg_order_value": float(row.avg_order_value),
                "cod_orders": row.cod_orders,
                "prepaid_orders": row.prepaid_orders,
                "prepaid_percentage": round(100 * row.prepaid_orders / row.order_count, 2) if row.order_count > 0 else 0
            }
            sales_data.append(period_data)
            
            # Accumulate totals
            for key in ["order_count", "unique_customers", "gross_revenue", "total_discount", "delivery_revenue", "net_revenue"]:
                total_stats[key] += row._asdict()[key]
                
        # Calculate summary statistics
        summary = {
            "total_orders": total_stats["order_count"],
            "unique_customers": total_stats["unique_customers"],
            "gross_revenue": float(total_stats["gross_revenue"]),
            "total_discount": float(total_stats["total_discount"]),
            "delivery_revenue": float(total_stats["delivery_revenue"]),
            "net_revenue": float(total_stats["net_revenue"]),
            "avg_order_value": float(total_stats["net_revenue"] / total_stats["order_count"]) if total_stats["order_count"] > 0 else 0
        }
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "group_by": group_by
            },
            "summary": summary,
            "data": sales_data
        }
        
    async def generate_user_activity_report(
        self,
        date: date
    ) -> Dict[str, Any]:
        """Generate user activity report for a specific date"""
        # User acquisition
        acquisition_query = """
        SELECT 
            COUNT(DISTINCT CASE WHEN role = 'buyer' THEN id END) as new_buyers,
            COUNT(DISTINCT CASE WHEN role = 'seller' THEN id END) as new_sellers,
            COUNT(DISTINCT CASE WHEN referred_by IS NOT NULL THEN id END) as referred_users
        FROM users
        WHERE DATE(created_at) = :date
        """
        
        acquisition = await self.db.execute(
            text(acquisition_query),
            {"date": date}
        )
        acquisition = acquisition.fetchone()._asdict()
        
        # Activity metrics
        activity_query = """
        SELECT 
            activity_type,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(*) as total_events
        FROM user_activities
        WHERE DATE(created_at) = :date
        GROUP BY activity_type
        """
        
        activities = await self.db.execute(
            text(activity_query),
            {"date": date}
        )
        
        activity_breakdown = {}
        for row in activities:
            activity_breakdown[row.activity_type] = {
                "unique_users": row.unique_users,
                "total_events": row.total_events
            }
            
        # Session metrics
        session_query = """
        WITH user_sessions AS (
            SELECT 
                user_id,
                session_id,
                MIN(created_at) as session_start,
                MAX(created_at) as session_end,
                COUNT(*) as page_views
            FROM user_activities
            WHERE DATE(created_at) = :date
            GROUP BY user_id, session_id
        )
        SELECT 
            COUNT(DISTINCT user_id) as daily_active_users,
            COUNT(DISTINCT session_id) as total_sessions,
            AVG(EXTRACT(EPOCH FROM (session_end - session_start))) as avg_session_duration,
            AVG(page_views) as avg_pages_per_session,
            COUNT(DISTINCT CASE WHEN page_views = 1 THEN session_id END)::float / 
                COUNT(DISTINCT session_id) * 100 as bounce_rate
        FROM user_sessions
        """
        
        sessions = await self.db.execute(
            text(session_query),
            {"date": date}
        )
        sessions = sessions.fetchone()._asdict()
        
        return {
            "date": date.isoformat(),
            "user_acquisition": acquisition,
            "activity_breakdown": activity_breakdown,
            "session_metrics": {
                "daily_active_users": sessions["daily_active_users"],
                "total_sessions": sessions["total_sessions"],
                "avg_session_duration_seconds": int(sessions["avg_session_duration"]) if sessions["avg_session_duration"] else 0,
                "avg_pages_per_session": float(sessions["avg_pages_per_session"]) if sessions["avg_pages_per_session"] else 0,
                "bounce_rate": float(sessions["bounce_rate"]) if sessions["bounce_rate"] else 0
            }
        }
        
    async def calculate_user_lifetime_value(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Calculate user lifetime value and related metrics"""
        query = """
        WITH user_orders AS (
            SELECT 
                COUNT(DISTINCT o.id) as total_orders,
                COALESCE(SUM(o.total_amount), 0) as total_spent,
                MIN(o.created_at) as first_order_date,
                MAX(o.created_at) as last_order_date,
                AVG(o.total_amount) as avg_order_value
            FROM orders o
            WHERE o.buyer_id = :user_id
            AND o.status IN ('confirmed', 'shipped', 'delivered')
        ),
        order_frequency AS (
            SELECT 
                CASE 
                    WHEN COUNT(DISTINCT DATE(created_at)) > 1
                    THEN EXTRACT(DAY FROM (MAX(created_at) - MIN(created_at))) / 
                         (COUNT(DISTINCT DATE(created_at)) - 1)
                    ELSE NULL
                END as avg_days_between_orders
            FROM orders
            WHERE buyer_id = :user_id
            AND status IN ('confirmed', 'shipped', 'delivered')
        ),
        category_preferences AS (
            SELECT 
                c.name as category,
                COUNT(DISTINCT oi.order_id) as order_count,
                SUM(oi.quantity * oi.price) as category_spent
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN products p ON oi.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE o.buyer_id = :user_id
            AND o.status IN ('confirmed', 'shipped', 'delivered')
            GROUP BY c.id, c.name
            ORDER BY category_spent DESC
            LIMIT 5
        )
        SELECT 
            uo.*,
            of.avg_days_between_orders,
            u.created_at as user_created_at,
            EXTRACT(DAY FROM (NOW() - u.created_at)) as account_age_days
        FROM user_orders uo, order_frequency of, users u
        WHERE u.id = :user_id
        """
        
        result = await self.db.execute(
            text(query),
            {"user_id": user_id}
        )
        user_data = result.fetchone()._asdict()
        
        # Get category preferences
        categories = await self.db.execute(
            text("""
            SELECT 
                c.name as category,
                COUNT(DISTINCT oi.order_id) as order_count,
                SUM(oi.quantity * oi.price) as category_spent
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN products p ON oi.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE o.buyer_id = :user_id
            AND o.status IN ('confirmed', 'shipped', 'delivered')
            GROUP BY c.id, c.name
            ORDER BY category_spent DESC
            LIMIT 5
            """),
            {"user_id": user_id}
        )
        
        # Calculate CLV (simplified)
        if user_data["avg_days_between_orders"] and user_data["avg_order_value"]:
            # Assume 2 year customer lifespan
            estimated_orders_per_year = 365 / user_data["avg_days_between_orders"]
            clv = float(user_data["avg_order_value"]) * estimated_orders_per_year * 2
        else:
            clv = float(user_data["total_spent"])
            
        return {
            "user_id": user_id,
            "lifetime_value": clv,
            "total_orders": user_data["total_orders"],
            "total_spent": float(user_data["total_spent"]),
            "avg_order_value": float(user_data["avg_order_value"]) if user_data["avg_order_value"] else 0,
            "avg_days_between_orders": int(user_data["avg_days_between_orders"]) if user_data["avg_days_between_orders"] else None,
            "account_age_days": int(user_data["account_age_days"]),
            "first_order_date": user_data["first_order_date"].isoformat() if user_data["first_order_date"] else None,
            "last_order_date": user_data["last_order_date"].isoformat() if user_data["last_order_date"] else None,
            "category_preferences": [
                {
                    "category": row.category,
                    "order_count": row.order_count,
                    "total_spent": float(row.category_spent)
                }
                for row in categories
            ]
        }
        
    async def generate_product_performance_report(
        self,
        date: date
    ) -> Dict[str, Any]:
        """Generate product performance report"""
        # Product metrics
        query = """
        WITH product_sales AS (
            SELECT 
                p.id,
                p.title,
                p.category_id,
                c.name as category_name,
                COUNT(DISTINCT oi.order_id) as order_count,
                SUM(oi.quantity) as units_sold,
                SUM(oi.quantity * oi.price) as revenue,
                AVG(oi.price) as avg_selling_price
            FROM products p
            JOIN categories c ON p.category_id = c.id
            LEFT JOIN order_items oi ON p.id = oi.product_id
            LEFT JOIN orders o ON oi.order_id = o.id
            WHERE DATE(o.created_at) = :date
            AND o.status IN ('confirmed', 'shipped', 'delivered')
            GROUP BY p.id, p.title, p.category_id, c.name
        ),
        product_views AS (
            SELECT 
                product_id,
                COUNT(DISTINCT user_id) as unique_viewers,
                COUNT(*) as total_views
            FROM product_views
            WHERE DATE(created_at) = :date
            GROUP BY product_id
        ),
        product_inventory AS (
            SELECT 
                p.id,
                p.stock as current_stock,
                p.status,
                CASE 
                    WHEN p.stock = 0 THEN 'out_of_stock'
                    WHEN p.stock < 10 THEN 'low_stock'
                    ELSE 'in_stock'
                END as stock_status
            FROM products p
        )
        SELECT 
            ps.*,
            COALESCE(pv.unique_viewers, 0) as unique_viewers,
            COALESCE(pv.total_views, 0) as total_views,
            pi.current_stock,
            pi.stock_status,
            CASE 
                WHEN pv.unique_viewers > 0 
                THEN ROUND(100.0 * ps.order_count / pv.unique_viewers, 2)
                ELSE 0
            END as conversion_rate
        FROM product_sales ps
        LEFT JOIN product_views pv ON ps.id = pv.product_id
        JOIN product_inventory pi ON ps.id = pi.id
        ORDER BY ps.revenue DESC NULLS LAST
        """
        
        products = await self.db.execute(
            text(query),
            {"date": date}
        )
        
        # Category summary
        category_query = """
        SELECT 
            c.name as category,
            COUNT(DISTINCT p.id) as product_count,
            COALESCE(SUM(oi.quantity), 0) as units_sold,
            COALESCE(SUM(oi.quantity * oi.price), 0) as revenue
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id
        LEFT JOIN order_items oi ON p.id = oi.product_id
        LEFT JOIN orders o ON oi.order_id = o.id
        WHERE DATE(o.created_at) = :date
        AND o.status IN ('confirmed', 'shipped', 'delivered')
        GROUP BY c.id, c.name
        ORDER BY revenue DESC
        """
        
        categories = await self.db.execute(
            text(category_query),
            {"date": date}
        )
        
        return {
            "date": date.isoformat(),
            "products": [
                {
                    "id": str(row.id),
                    "title": row.title,
                    "category": row.category_name,
                    "order_count": row.order_count or 0,
                    "units_sold": row.units_sold or 0,
                    "revenue": float(row.revenue) if row.revenue else 0,
                    "avg_selling_price": float(row.avg_selling_price) if row.avg_selling_price else 0,
                    "unique_viewers": row.unique_viewers,
                    "total_views": row.total_views,
                    "conversion_rate": float(row.conversion_rate),
                    "current_stock": row.current_stock,
                    "stock_status": row.stock_status
                }
                for row in products
            ],
            "category_summary": [
                {
                    "category": row.category,
                    "product_count": row.product_count,
                    "units_sold": row.units_sold,
                    "revenue": float(row.revenue)
                }
                for row in categories
            ]
        }
        
    async def _get_daily_sales(
        self,
        seller_id: str,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Get daily sales data for seller"""
        query = """
        SELECT 
            DATE(o.created_at) as date,
            COUNT(DISTINCT o.id) as orders,
            SUM(o.total_amount) as revenue,
            COUNT(DISTINCT o.buyer_id) as customers
        FROM orders o
        WHERE o.seller_id = :seller_id
        AND o.created_at >= :start_date
        AND o.created_at < :end_date + INTERVAL '1 day'
        AND o.status IN ('confirmed', 'shipped', 'delivered')
        GROUP BY DATE(o.created_at)
        ORDER BY date
        """
        
        result = await self.db.execute(
            text(query),
            {"seller_id": seller_id, "start_date": start_date, "end_date": end_date}
        )
        
        return [
            {
                "date": row.date.isoformat(),
                "orders": row.orders,
                "revenue": float(row.revenue),
                "customers": row.customers
            }
            for row in result
        ]
        
    async def _get_top_products(
        self,
        seller_id: str,
        start_date: date,
        end_date: date,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top performing products for seller"""
        query = """
        SELECT 
            p.id,
            p.title,
            p.primary_image,
            COUNT(DISTINCT oi.order_id) as order_count,
            SUM(oi.quantity) as units_sold,
            SUM(oi.quantity * oi.price) as revenue,
            p.stock as current_stock
        FROM products p
        JOIN order_items oi ON p.id = oi.product_id
        JOIN orders o ON oi.order_id = o.id
        WHERE p.seller_id = :seller_id
        AND o.created_at >= :start_date
        AND o.created_at < :end_date + INTERVAL '1 day'
        AND o.status IN ('confirmed', 'shipped', 'delivered')
        GROUP BY p.id, p.title, p.primary_image, p.stock
        ORDER BY revenue DESC
        LIMIT :limit
        """
        
        result = await self.db.execute(
            text(query),
            {
                "seller_id": seller_id,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit
            }
        )
        
        return [
            {
                "id": str(row.id),
                "title": row.title,
                "image": row.primary_image,
                "order_count": row.order_count,
                "units_sold": row.units_sold,
                "revenue": float(row.revenue),
                "current_stock": row.current_stock
            }
            for row in result
        ]
        
    async def _get_customer_analytics(
        self,
        seller_id: str,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get customer analytics for seller"""
        query = """
        WITH customer_data AS (
            SELECT 
                o.buyer_id,
                COUNT(DISTINCT o.id) as order_count,
                SUM(o.total_amount) as total_spent,
                MIN(o.created_at) as first_order,
                MAX(o.created_at) as last_order
            FROM orders o
            WHERE o.seller_id = :seller_id
            AND o.created_at >= :start_date
            AND o.created_at < :end_date + INTERVAL '1 day'
            AND o.status IN ('confirmed', 'shipped', 'delivered')
            GROUP BY o.buyer_id
        )
        SELECT 
            COUNT(DISTINCT buyer_id) as total_customers,
            COUNT(DISTINCT CASE WHEN order_count = 1 THEN buyer_id END) as new_customers,
            COUNT(DISTINCT CASE WHEN order_count > 1 THEN buyer_id END) as repeat_customers,
            AVG(total_spent) as avg_customer_value,
            MAX(total_spent) as highest_customer_value
        FROM customer_data
        """
        
        result = await self.db.execute(
            text(query),
            {"seller_id": seller_id, "start_date": start_date, "end_date": end_date}
        )
        
        customer_stats = result.fetchone()._asdict()
        
        # Top customers
        top_customers_query = """
        SELECT 
            u.id,
            u.name,
            u.email,
            COUNT(DISTINCT o.id) as order_count,
            SUM(o.total_amount) as total_spent
        FROM orders o
        JOIN users u ON o.buyer_id = u.id
        WHERE o.seller_id = :seller_id
        AND o.created_at >= :start_date
        AND o.created_at < :end_date + INTERVAL '1 day'
        AND o.status IN ('confirmed', 'shipped', 'delivered')
        GROUP BY u.id, u.name, u.email
        ORDER BY total_spent DESC
        LIMIT 10
        """
        
        top_customers = await self.db.execute(
            text(top_customers_query),
            {"seller_id": seller_id, "start_date": start_date, "end_date": end_date}
        )
        
        return {
            "summary": {
                "total_customers": customer_stats["total_customers"],
                "new_customers": customer_stats["new_customers"],
                "repeat_customers": customer_stats["repeat_customers"],
                "repeat_rate": round(100 * customer_stats["repeat_customers"] / customer_stats["total_customers"], 2) if customer_stats["total_customers"] > 0 else 0,
                "avg_customer_value": float(customer_stats["avg_customer_value"]) if customer_stats["avg_customer_value"] else 0,
                "highest_customer_value": float(customer_stats["highest_customer_value"]) if customer_stats["highest_customer_value"] else 0
            },
            "top_customers": [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "email": row.email,
                    "order_count": row.order_count,
                    "total_spent": float(row.total_spent)
                }
                for row in top_customers
            ]
        }


# """Analytics aggregation service"""

# from typing import Dict, Any, List, Optional
# from datetime import datetime, timedelta, date
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, func, and_, or_, distinct, case
# import logging

# from app.models.order import Order, OrderItem
# from app.models.user import User
# from app.models.product import Product
# from app.models.analytics import UserActivity, ProductView

# logger = logging.getLogger(__name__)

# class AnalyticsService:
#     """Service for generating analytics and reports"""
    
#     def __init__(self, db: AsyncSession):
#         self.db = db
        
#     async def get_sales_analytics(
#         self,
#         start_date: date,
#         end_date: date,
#         seller_id: Optional[str] = None
#     ) -> Dict[str, Any]:
#         """Get sales analytics for date range"""
#         query = select(
#             func.date_trunc('day', Order.created_at).label('date'),
#             func.count(distinct(Order.id)).label('order_count'),
#             func.sum(Order.total_amount).label('revenue'),
#             func.avg(Order.total_amount).label('avg_order_value')
#         ).where(
#             and_(
#                 Order.created_at >= start_date,
#                 Order.created_at < end_date + timedelta(days=1),
#                 Order.status.in_(['confirmed', 'shipped', 'delivered'])
#             )
#         )
        
#         if seller_id:
#             query = query.where(Order.seller_id == seller_id)
            
#         query = query.group_by(func.date_trunc('day', Order.created_at))
#         query = query.order_by(func.date_trunc('day', Order.created_at))
        
#         result = await self.db.execute(query)
#         daily_sales = result.all()
        
#         # Calculate totals
#         total_query = select(
#             func.count(distinct(Order.id)).label('total_orders'),
#             func.sum(Order.total_amount).label('total_revenue'),
#             func.avg(Order.total_amount).label('avg_order_value')
#         ).where(
#             and_(
#                 Order.created_at >= start_date,
#                 Order.created_at < end_date + timedelta(days=1),
#                 Order.status.in_(['confirmed', 'shipped', 'delivered'])
#             )
#         )
        
#         if seller_id:
#             total_query = total_query.where(Order.seller_id == seller_id)
            
#         totals = await self.db.execute(total_query)
#         totals = totals.one()
        
#         return {
#             "period": {
#                 "start": start_date.isoformat(),
#                 "end": end_date.isoformat()
#             },
#             "summary": {
#                 "total_orders": totals.total_orders or 0,
#                 "total_revenue": float(totals.total_revenue or 0),
#                 "avg_order_value": float(totals.avg_order_value or 0)
#             },
#             "daily_breakdown": [
#                 {
#                     "date": row.date.date().isoformat(),
#                     "orders": row.order_count,
#                     "revenue": float(row.revenue),
#                     "avg_order_value": float(row.avg_order_value)
#                 }
#                 for row in daily_sales
#             ]
#         }
        
#     async def get_user_analytics(
#         self,
#         start_date: date,
#         end_date: date
#     ) -> Dict[str, Any]:
#         """Get user analytics"""
#         # New users
#         new_users_query = select(
#             func.date_trunc('day', User.created_at).label('date'),
#             func.count(User.id).label('count')
#         ).where(
#             and_(
#                 User.created_at >= start_date,
#                 User.created_at < end_date + timedelta(days=1)
#             )
#         ).group_by(func.date_trunc('day', User.created_at))
        
#         new_users = await self.db.execute(new_users_query)
#         new_users = new_users.all()
        
#         # Active users (users who placed orders)
#         active_users_query = select(
#             func.date_trunc('day', Order.created_at).label('date'),
#             func.count(distinct(Order.buyer_id)).label('count')
#         ).where(
#             and_(
#                 Order.created_at >= start_date,
#                 Order.created_at < end_date + timedelta(days=1)
#             )
#         ).group_by(func.date_trunc('day', Order.created_at))
        
#         active_users = await self.db.execute(active_users_query)
#         active_users = active_users.all()
        
#         # Churn rate calculation
#         # Users who haven't ordered in last 30 days
#         thirty_days_ago = end_date - timedelta(days=30)
#         sixty_days_ago = end_date - timedelta(days=60)
        
#         # Users who ordered 30-60 days ago but not in last 30 days
#         churned_users_query = select(
#             func.count(distinct(Order.buyer_id))
#         ).where(
#             and_(
#                 Order.created_at >= sixty_days_ago,
#                 Order.created_at < thirty_days_ago,
#                 ~Order.buyer_id.in_(
#                     select(Order.buyer_id).where(
#                         Order.created_at >= thirty_days_ago
#                     )
#                 )
#             )
#         )
        
#         churned_count = await self.db.execute(churned_users_query)
#         churned_count = churned_count.scalar()
        
#         # Total users who ordered 30-60 days ago
#         total_users_query = select(
#             func.count(distinct(Order.buyer_id))
#         ).where(
#             and_(
#                 Order.created_at >= sixty_days_ago,
#                 Order.created_at < thirty_days_ago
#             )
#         )
        
#         total_count = await self.db.execute(total_users_query)
#         total_count = total_count.scalar()
        
#         churn_rate = (churned_count / total_count * 100) if total_count > 0 else 0
        
#         return {
#             "period": {
#                 "start": start_date.isoformat(),
#                 "end": end_date.isoformat()
#             },
#             "new_users": [
#                 {
#                     "date": row.date.date().isoformat(),
#                     "count": row.count
#                 }
#                 for row in new_users
#             ],
#             "active_users": [
#                 {
#                     "date": row.date.date().isoformat(),
#                     "count": row.count
#                 }
#                 for row in active_users
#             ],
#             "churn_rate": round(churn_rate, 2)
#         }
        
#     async def get_product_analytics(
#         self,
#         product_id: str,
#         start_date: date,
#         end_date: date
#     ) -> Dict[str, Any]:
#         """Get product-specific analytics"""
#         # Views
#         views_query = select(
#             func.count(ProductView.id).label('total_views'),
#             func.count(distinct(ProductView.user_id)).label('unique_viewers')
#         ).where(
#             and_(
#                 ProductView.product_id == product_id,
#                 ProductView.created_at >= start_date,
#                 ProductView.created_at < end_date + timedelta(days=1)
#             )
#         )
        
#         views = await self.db.execute(views_query)
#         views = views.one()
        
#         # Purchases
#         purchases_query = select(
#             func.count(distinct(OrderItem.order_id)).label('order_count'),
#             func.sum(OrderItem.quantity).label('units_sold'),
#             func.sum(OrderItem.quantity * OrderItem.price).label('revenue')
#         ).select_from(OrderItem).join(Order).where(
#             and_(
#                 OrderItem.product_id == product_id,
#                 Order.created_at >= start_date,
#                 Order.created_at < end_date + timedelta(days=1),
#                 Order.status.in_(['confirmed', 'shipped', 'delivered'])
#             )
#         )
        
#         purchases = await self.db.execute(purchases_query)
#         purchases = purchases.one()
        
#         # Conversion rate
#         conversion_rate = 0
#         if views.unique_viewers > 0:
#             conversion_rate = (purchases.order_count / views.unique_viewers) * 100
            
#         return {
#             "product_id": product_id,
#             "period": {
#                 "start": start_date.isoformat(),
#                 "end": end_date.isoformat()
#             },
#             "metrics": {
#                 "total_views": views.total_views or 0,
#                 "unique_viewers": views.unique_viewers or 0,
#                 "orders": purchases.order_count or 0,
#                 "units_sold": purchases.units_sold or 0,
#                 "revenue": float(purchases.revenue or 0),
#                 "conversion_rate": round(conversion_rate, 2)
#             }
#         }
        
#     async def generate_weekly_report(self) -> Dict[str, Any]:
#         """Generate weekly analytics report"""
#         end_date = date.today()
#         start_date = end_date - timedelta(days=7)
        
#         # Sales analytics
#         sales = await self.get_sales_analytics(start_date, end_date)
        
#         # User analytics
#         users = await self.get_user_analytics(start_date, end_date)
        
#         # Top products
#         top_products_query = select(
#             Product.id,
#             Product.title,
#             func.sum(OrderItem.quantity).label('units_sold'),
#             func.sum(OrderItem.quantity * OrderItem.price).label('revenue')
#         ).select_from(OrderItem).join(Order).join(Product).where(
#             and_(
#                 Order.created_at >= start_date,
#                 Order.created_at < end_date + timedelta(days=1),
#                 Order.status.in_(['confirmed', 'shipped', 'delivered'])
#             )
#         ).group_by(Product.id, Product.title).order_by(
#             func.sum(OrderItem.quantity * OrderItem.price).desc()
#         ).limit(10)
        
#         top_products = await self.db.execute(top_products_query)
#         top_products = top_products.all()
        
#         return {
#             "report_date": date.today().isoformat(),
#             "period": {
#                 "start": start_date.isoformat(),
#                 "end": end_date.isoformat()
#             },
#             "sales": sales["summary"],
#             "users": {
#                 "new_users": sum(u["count"] for u in users["new_users"]),
#                 "active_users": sum(u["count"] for u in users["active_users"]),
#                 "churn_rate": users["churn_rate"]
#             },
#             "top_products": [
#                 {
#                     "id": str(p.id),
#                     "title": p.title,
#                     "units_sold": p.units_sold,
#                     "revenue": float(p.revenue)
#                 }
#                 for p in top_products
#             ]
#         }
