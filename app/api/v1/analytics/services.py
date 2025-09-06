"""Analytics service layer"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.orm import selectinload
import pandas as pd
import numpy as np

from app.models import Order, OrderItem, Product, User
from app.core.cache import cache, cached
from .schemas import DateRangeFilter, SalesAnalytics, SellerDashboardAnalytics

class AnalyticsService:
    """Analytics service for business intelligence"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    @cached(key_prefix="analytics:sales", expire=3600)
    async def get_sales_analytics(
        self,
        seller_id: Optional[str] = None,
        date_range: Optional[DateRangeFilter] = None
    ) -> SalesAnalytics:
        """Get sales analytics"""
        query = select(
            func.sum(Order.total_amount).label("revenue"),
            func.count(Order.id).label("orders"),
            func.avg(Order.total_amount).label("avg_order_value"),
            func.sum(func.array_length(Order.items, 1)).label("products_sold")
        ).where(Order.status == "delivered")
        
        if seller_id:
            query = query.where(Order.seller_id == seller_id)
            
        if date_range:
            query = query.where(
                and_(
                    Order.created_at >= date_range.start_date,
                    Order.created_at <= date_range.end_date
                )
            )
            
        result = await self.db.execute(query)
        data = result.one()
        
        # Calculate growth percentage
        if date_range:
            previous_period = DateRangeFilter(
                start_date=date_range.start_date - timedelta(days=30),
                end_date=date_range.start_date - timedelta(days=1)
            )
            previous_analytics = await self.get_sales_analytics(seller_id, previous_period)
            growth = self._calculate_growth(
                data.revenue or 0,
                previous_analytics.total_revenue
            )
        else:
            growth = 0
            
        return SalesAnalytics(
            total_revenue=data.revenue or Decimal("0"),
            total_orders=data.orders or 0,
            average_order_value=data.avg_order_value or Decimal("0"),
            total_products_sold=data.products_sold or 0,
            growth_percentage=growth
        )
        
    async def get_product_performance(
        self,
        seller_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top performing products"""
        query = """
        SELECT 
            p.id,
            p.title,
            COUNT(oi.id) as units_sold,
            SUM(oi.total_price) as revenue,
            p.view_count,
            CASE 
                WHEN p.view_count > 0 
                THEN (COUNT(oi.id)::float / p.view_count * 100)
                ELSE 0 
            END as conversion_rate
        FROM products p
        LEFT JOIN order_items oi ON p.id = oi.product_id
        LEFT JOIN orders o ON oi.order_id = o.id AND o.status = 'delivered'
        WHERE p.status = 'active'
        """
        
        if seller_id:
            query += f" AND p.seller_id = '{seller_id}'"
            
        query += """
        GROUP BY p.id, p.title, p.view_count
        ORDER BY revenue DESC NULLS LAST
        LIMIT %s
        """
        
        result = await self.db.execute(query, (limit,))
        return result.fetchall()
        
    async def track_user_behavior(
        self,
        event_data: Dict[str, Any]
    ) -> None:
        """Track user behavior events"""
        # Note: AnalyticsEvent model usage commented out until model is available
        # event = AnalyticsEvent(
        #     user_id=event_data.get("user_id"),
        #     session_id=event_data["session_id"],
        #     event_type=event_data["event_type"],
        #     event_data=event_data.get("metadata", {}),
        #     ip_address=event_data.get("ip_address"),
        #     user_agent=event_data.get("user_agent")
        # )
        # self.db.add(event)
        await self.db.commit()
        
        # Process event for real-time analytics
        # await self._process_event_analytics(event)
        
    async def get_seller_dashboard_analytics(
        self,
        seller_id: str,
        date_range: Optional[DateRangeFilter] = None
    ) -> SellerDashboardAnalytics:
        """Get comprehensive seller dashboard analytics"""
        # Get various analytics
        sales = await self.get_sales_analytics(seller_id, date_range)
        products = await self.get_product_performance(seller_id)
        customers = await self.get_customer_analytics(seller_id, date_range)
        revenue_trend = await self.get_revenue_by_date(seller_id, date_range)
        order_status = await self.get_orders_by_status(seller_id, date_range)
        category_perf = await self.get_category_performance(seller_id, date_range)
        
        return SellerDashboardAnalytics(
            sales_analytics=sales,
            top_products=products,
            customer_analytics=customers,
            revenue_by_date=revenue_trend,
            orders_by_status=order_status,
            category_performance=category_perf
        )
        
    async def get_customer_analytics(
        self,
        seller_id: Optional[str] = None,
        date_range: Optional[DateRangeFilter] = None
    ) -> Dict[str, Any]:
        """Get customer analytics"""
        # Total customers
        customer_query = select(func.count(func.distinct(Order.buyer_id)))
        if seller_id:
            customer_query = customer_query.where(Order.seller_id == seller_id)
            
        total_customers = await self.db.scalar(customer_query)
        
        # New vs returning customers
        new_customers_query = """
        SELECT COUNT(DISTINCT buyer_id) 
        FROM orders 
        WHERE created_at >= %s
        AND buyer_id NOT IN (
            SELECT DISTINCT buyer_id 
            FROM orders 
            WHERE created_at < %s
        )
        """
        
        if date_range:
            new_customers = await self.db.execute(
                new_customers_query,
                (date_range.start_date, date_range.start_date)
            )
            new_count = new_customers.scalar()
        else:
            new_count = 0
            
        return {
            "total_customers": total_customers,
            "new_customers": new_count,
            "returning_customers": total_customers - new_count,
            "customer_lifetime_value": await self._calculate_clv(seller_id),
            "churn_rate": await self._calculate_churn_rate(seller_id)
        }
        
    async def _calculate_clv(self, seller_id: Optional[str] = None) -> Decimal:
        """Calculate customer lifetime value"""
        query = """
        SELECT AVG(customer_total) as clv
        FROM (
            SELECT buyer_id, SUM(total_amount) as customer_total
            FROM orders
            WHERE status = 'delivered'
            {seller_filter}
            GROUP BY buyer_id
        ) as customer_totals
        """
        
        seller_filter = f"AND seller_id = '{seller_id}'" if seller_id else ""
        result = await self.db.execute(query.format(seller_filter=seller_filter))
        return result.scalar() or Decimal("0")
        
    async def _calculate_churn_rate(self, seller_id: Optional[str] = None) -> float:
        """Calculate customer churn rate"""
        # Customers who haven't ordered in last 90 days
        query = """
        SELECT 
            COUNT(DISTINCT CASE 
                WHEN MAX(created_at) < NOW() - INTERVAL '90 days' 
                THEN buyer_id 
            END)::float / COUNT(DISTINCT buyer_id) * 100 as churn_rate
        FROM orders
        WHERE status = 'delivered'
        """
        
        if seller_id:
            query += f" AND seller_id = '{seller_id}'"
            
        result = await self.db.execute(query)
        return result.scalar() or 0.0
        
    async def get_revenue_by_date(
        self,
        seller_id: Optional[str] = None,
        date_range: Optional[DateRangeFilter] = None
    ) -> List[Dict[str, Any]]:
        """Get revenue trend by date"""
        query = """
        SELECT 
            DATE(created_at) as date,
            SUM(total_amount) as revenue,
            COUNT(*) as orders
        FROM orders
        WHERE status = 'delivered'
        """
        
        conditions = []
        if seller_id:
            conditions.append(f"seller_id = '{seller_id}'")
        if date_range:
            conditions.append(f"created_at >= '{date_range.start_date}'")
            conditions.append(f"created_at <= '{date_range.end_date}'")
            
        if conditions:
            query += " AND " + " AND ".join(conditions)
            
        query += " GROUP BY DATE(created_at) ORDER BY date"
        
        result = await self.db.execute(query)
        return [
            {"date": row.date, "revenue": row.revenue, "orders": row.orders}
            for row in result.fetchall()
        ]
        
    async def get_orders_by_status(
        self,
        seller_id: Optional[str] = None,
        date_range: Optional[DateRangeFilter] = None
    ) -> Dict[str, int]:
        """Get order count by status"""
        query = select(
            Order.status,
            func.count(Order.id)
        ).group_by(Order.status)
        
        if seller_id:
            query = query.where(Order.seller_id == seller_id)
        if date_range:
            query = query.where(
                and_(
                    Order.created_at >= date_range.start_date,
                    Order.created_at <= date_range.end_date
                )
            )
            
        result = await self.db.execute(query)
        return dict(result.fetchall())
        
    async def get_category_performance(
        self,
        seller_id: Optional[str] = None,
        date_range: Optional[DateRangeFilter] = None
    ) -> List[Dict[str, Any]]:
        """Get performance by category"""
        query = """
        SELECT 
            c.name as category,
            COUNT(DISTINCT p.id) as products,
            SUM(oi.quantity) as units_sold,
            SUM(oi.total_price) as revenue
        FROM categories c
        JOIN products p ON c.id = p.category_id
        LEFT JOIN order_items oi ON p.id = oi.product_id
        LEFT JOIN orders o ON oi.order_id = o.id AND o.status = 'delivered'
        WHERE p.status = 'active'
        """
        
        if seller_id:
            query += f" AND p.seller_id = '{seller_id}'"
            
        query += " GROUP BY c.id, c.name ORDER BY revenue DESC"
        
        result = await self.db.execute(query)
        return [
            {
                "category": row.category,
                "products": row.products,
                "units_sold": row.units_sold or 0,
                "revenue": row.revenue or Decimal("0")
            }
            for row in result.fetchall()
        ]
        
    def _calculate_growth(self, current: Decimal, previous: Decimal) -> float:
        """Calculate growth percentage"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return float((current - previous) / previous * 100)
        
    async def _process_event_analytics(self, event_data: Dict[str, Any]) -> None:
        """Process analytics event for real-time insights"""
        # Note: Implementation commented out until AnalyticsEvent model is available
        # Update real-time metrics in Redis
        # if event_data.get("event_type") == "product_view":
        #     await cache.increment(f"analytics:views:{event_data.get('product_id')}")
        # elif event_data.get("event_type") == "add_to_cart":
        #     await cache.increment(f"analytics:cart_adds:{event_data.get('product_id')}")
        pass
