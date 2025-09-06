"""Price tracking service for price history and alerts"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from decimal import Decimal
import logging

from app.models.product import Product, PriceHistory
from app.models.user import User
from app.models.price_alert import PriceAlert, PriceAlertStatus

logger = logging.getLogger(__name__)

class PriceTrackingService:
    """Service for tracking price changes and managing alerts"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def track_price_change(
        self,
        product_id: str,
        old_price: Decimal,
        new_price: Decimal,
        change_reason: Optional[str] = None
    ) -> PriceHistory:
        """Track product price change"""
        # Calculate change percentage
        if old_price > 0:
            change_percentage = ((new_price - old_price) / old_price) * 100
        else:
            change_percentage = 0
            
        # Create price history record
        price_history = PriceHistory(
            product_id=product_id,
            old_price=old_price,
            new_price=new_price,
            change_percentage=change_percentage,
            change_reason=change_reason or "Manual update"
        )
        
        self.db.add(price_history)
        await self.db.commit()
        
        # Check and trigger price alerts
        await self._check_price_alerts(product_id, new_price, change_percentage)
        
        return price_history
        
    async def get_price_history(
        self,
        product_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get price history for a product"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(PriceHistory).where(
            and_(
                PriceHistory.product_id == product_id,
                PriceHistory.created_at >= cutoff_date
            )
        ).order_by(PriceHistory.created_at.desc())
        
        result = await self.db.execute(query)
        history = result.scalars().all()
        
        return [
            {
                "date": h.created_at.isoformat(),
                "old_price": float(h.old_price),
                "new_price": float(h.new_price),
                "change_percentage": float(h.change_percentage),
                "change_reason": h.change_reason
            }
            for h in history
        ]
        
    async def create_price_alert(
        self,
        user_id: str,
        product_id: str,
        target_price: Decimal,
        alert_type: str = "drop_below"
    ) -> PriceAlert:
        """Create a price alert for user"""
        # Check if similar alert exists
        existing = await self.db.execute(
            select(PriceAlert).where(
                and_(
                    PriceAlert.user_id == user_id,
                    PriceAlert.product_id == product_id,
                    PriceAlert.status == PriceAlertStatus.ACTIVE,
                    PriceAlert.alert_type == alert_type
                )
            )
        )
        
        if existing.scalar_one_or_none():
            raise ValueError("Similar price alert already exists")
            
        # Get current product price
        product = await self.db.get(Product, product_id)
        if not product:
            raise ValueError("Product not found")
            
        # Create alert
        alert = PriceAlert(
            user_id=user_id,
            product_id=product_id,
            target_price=target_price,
            current_price=product.price,
            alert_type=alert_type,
            status=PriceAlertStatus.ACTIVE
        )
        
        self.db.add(alert)
        await self.db.commit()
        
        return alert
        
    async def get_user_price_alerts(
        self,
        user_id: str,
        status: Optional[PriceAlertStatus] = None
    ) -> List[Dict[str, Any]]:
        """Get user's price alerts"""
        query = select(PriceAlert).where(PriceAlert.user_id == user_id)
        
        if status:
            query = query.where(PriceAlert.status == status)
            
        query = query.order_by(PriceAlert.created_at.desc())
        
        result = await self.db.execute(query)
        alerts = result.scalars().all()
        
        # Load related products
        alert_data = []
        for alert in alerts:
            product = await self.db.get(Product, alert.product_id)
            alert_data.append({
                "id": str(alert.id),
                "product": {
                    "id": str(product.id),
                    "title": product.title,
                    "current_price": float(product.price),
                    "image": product.primary_image
                },
                "target_price": float(alert.target_price),
                "alert_type": alert.alert_type,
                "status": alert.status.value,
                "created_at": alert.created_at.isoformat(),
                "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None
            })
            
        return alert_data
        
    async def _check_price_alerts(
        self,
        product_id: str,
        new_price: Decimal,
        change_percentage: float
    ):
        """Check and trigger price alerts for a product"""
        # Get active alerts for this product
        alerts = await self.db.execute(
            select(PriceAlert).where(
                and_(
                    PriceAlert.product_id == product_id,
                    PriceAlert.status == PriceAlertStatus.ACTIVE
                )
            )
        )
        
        alerts = alerts.scalars().all()
        
        for alert in alerts:
            triggered = False
            
            if alert.alert_type == "drop_below" and new_price <= alert.target_price:
                triggered = True
            elif alert.alert_type == "rise_above" and new_price >= alert.target_price:
                triggered = True
            elif alert.alert_type == "any_change" and abs(change_percentage) >= 5:
                triggered = True
                
            if triggered:
                # Update alert status
                alert.status = PriceAlertStatus.TRIGGERED
                alert.triggered_at = datetime.utcnow()
                alert.triggered_price = new_price
                
                # Send notification
                await self._send_price_alert_notification(alert, new_price)
                
        await self.db.commit()
        
    async def _send_price_alert_notification(
        self,
        alert: PriceAlert,
        new_price: Decimal
    ):
        """Send price alert notification to user"""
        from app.tasks.push_notification_tasks import send_push_notification_task
        
        # Get product details
        product = await self.db.get(Product, alert.product_id)
        if not product:
            return
            
        # Prepare notification
        if alert.alert_type == "drop_below":
            title = "Price Drop Alert! 📉"
            message = f"{product.title} is now ₹{new_price} (was ₹{alert.current_price})"
        elif alert.alert_type == "rise_above":
            title = "Price Increase Alert! 📈"
            message = f"{product.title} is now ₹{new_price} (was ₹{alert.current_price})"
        else:
            title = "Price Change Alert! 🔔"
            message = f"{product.title} price changed to ₹{new_price}"
            
        # Send notification
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
        
    async def analyze_price_trends(
        self,
        category_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Analyze price trends for products"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Base query for price changes
        query = """
        WITH price_changes AS (
            SELECT 
                p.id,
                p.title,
                p.category_id,
                c.name as category_name,
                ph.old_price,
                ph.new_price,
                ph.change_percentage,
                ph.created_at
            FROM price_history ph
            JOIN products p ON ph.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE ph.created_at >= :cutoff_date
        """
        
        params = {"cutoff_date": cutoff_date}
        
        if category_id:
            query += " AND p.category_id = :category_id"
            params["category_id"] = category_id
            
        query += """
        ),
        trend_summary AS (
            SELECT 
                COUNT(DISTINCT CASE WHEN change_percentage < -5 THEN id END) as products_decreased,
                COUNT(DISTINCT CASE WHEN change_percentage > 5 THEN id END) as products_increased,
                COUNT(DISTINCT CASE WHEN ABS(change_percentage) <= 5 THEN id END) as products_stable,
                AVG(change_percentage) as avg_change_percentage
            FROM price_changes
        ),
        biggest_changes AS (
            SELECT DISTINCT ON (id)
                id,
                title,
                category_name,
                old_price,
                new_price,
                change_percentage
            FROM price_changes
            ORDER BY id, ABS(change_percentage) DESC
        )
        SELECT 
            ts.*,
            (
                SELECT json_agg(bc.* ORDER BY bc.change_percentage)
                FROM biggest_changes bc
                WHERE bc.change_percentage < -10
                LIMIT 10
            ) as biggest_drops,
            (
                SELECT json_agg(bc.* ORDER BY bc.change_percentage DESC)
                FROM biggest_changes bc
                WHERE bc.change_percentage > 10
                LIMIT 10
            ) as biggest_increases
        FROM trend_summary ts
        """
        
        result = await self.db.execute(text(query), params)
        data = result.fetchone()._asdict()
        
        return {
            "period_days": days,
            "category_id": category_id,
            "summary": {
                "products_with_price_drop": data["products_decreased"] or 0,
                "products_with_price_increase": data["products_increased"] or 0,
                "products_with_stable_price": data["products_stable"] or 0,
                "avg_change_percentage": float(data["avg_change_percentage"]) if data["avg_change_percentage"] else 0
            },
            "biggest_drops": data["biggest_drops"] or [],
            "biggest_increases": data["biggest_increases"] or []
        }
        
    async def suggest_optimal_price(
        self,
        product_id: str
    ) -> Dict[str, Any]:
        """Suggest optimal price based on market data"""
        product = await self.db.get(Product, product_id)
        if not product:
            raise ValueError("Product not found")
            
        # Get competitor prices (similar products)
        competitor_query = """
        SELECT 
            p.price,
            p.rating,
            p.review_count,
            p.purchase_count
        FROM products p
        WHERE p.category_id = :category_id
        AND p.id != :product_id
        AND p.status = 'active'
        AND p.price BETWEEN :min_price AND :max_price
        """
        
        min_price = float(product.price) * 0.5
        max_price = float(product.price) * 2.0
        
        competitors = await self.db.execute(
            text(competitor_query),
            {
                "category_id": product.category_id,
                "product_id": product_id,
                "min_price": min_price,
                "max_price": max_price
            }
        )
        
        competitor_prices = []
        for comp in competitors:
            # Weight by popularity (rating and purchase count)
            weight = (comp.rating or 3) * (comp.purchase_count or 1)
            competitor_prices.extend([float(comp.price)] * int(weight))
            
        if not competitor_prices:
            return {
                "current_price": float(product.price),
                "suggested_price": float(product.price),
                "confidence": "low",
                "reason": "Insufficient market data"
            }
            
        # Calculate percentiles
        import numpy as np
        prices_array = np.array(competitor_prices)
        
        p25 = np.percentile(prices_array, 25)
        p50 = np.percentile(prices_array, 50)
        p75 = np.percentile(prices_array, 75)
        
        current_price = float(product.price)
        
        # Determine suggested price based on product performance
        if product.rating and product.rating >= 4.5:
            # High-rated product can command premium
            suggested_price = p75
            reason = "High product rating allows premium pricing"
        elif product.purchase_count and product.purchase_count > 100:
            # Popular product, price at median
            suggested_price = p50
            reason = "Popular product, competitive pricing recommended"
        else:
            # New or less popular product, competitive pricing
            suggested_price = p25
            reason = "Competitive pricing to attract customers"
            
        # Don't suggest extreme changes
        max_change = current_price * 0.3
        if abs(suggested_price - current_price) > max_change:
            if suggested_price > current_price:
                suggested_price = current_price + max_change
            else:
                suggested_price = current_price - max_change
            reason += " (limited to 30% change)"
            
        return {
            "current_price": current_price,
            "suggested_price": round(suggested_price, 2),
            "market_percentiles": {
                "p25": round(p25, 2),
                "p50": round(p50, 2),
                "p75": round(p75, 2)
            },
            "confidence": "high" if len(competitor_prices) > 50 else "medium",
            "reason": reason,
            "competitors_analyzed": len(set(competitor_prices))
        }



# """Price tracking service"""

# from typing import List, Dict, Any, Optional
# from datetime import datetime, timedelta
# from decimal import Decimal
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, and_

# from app.models import Product, PriceHistory
# from app.services.notification import NotificationService

# class PriceTrackingService:
#     """Service for tracking price changes"""
    
#     def __init__(self, db: AsyncSession):
#         self.db = db
#         self.notification_service = NotificationService(db)
        
#     async def record_price_change(
#         self,
#         product: Product,
#         new_price: Decimal,
#         new_mrp: Optional[Decimal],
#         user_id: str,
#         reason: Optional[str] = None
#     ) -> None:
#         """Record price change"""
#         # Create history entry
#         history = PriceHistory(
#             product_id=product.id,
#             old_price=product.price,
#             new_price=new_price,
#             old_mrp=product.mrp,
#             new_mrp=new_mrp,
#             changed_by=user_id,
#             reason=reason
#         )
        
#         self.db.add(history)
        
#         # Update product
#         product.price = new_price
#         if new_mrp is not None:
#             product.mrp = new_mrp
            
#         # Check for price drop alerts
#         if new_price < history.old_price:
#             await self._send_price_drop_alerts(product, history)
            
#         await self.db.commit()
        
#     async def get_price_history(
#         self,
#         product_id: uuid.UUID,
#         days: int = 30
#     ) -> List[Dict[str, Any]]:
#         """Get price history for product"""
#         start_date = datetime.utcnow() - timedelta(days=days)
        
#         history = await self.db.execute(
#             select(PriceHistory)
#             .where(
#                 and_(
#                     PriceHistory.product_id == product_id,
#                     PriceHistory.created_at >= start_date
#                 )
#             )
#             .order_by(PriceHistory.created_at.desc())
#         )
        
#         return [
#             {
#                 "date": h.created_at,
#                 "old_price": h.old_price,
#                 "new_price": h.new_price,
#                 "change_percentage": float(
#                     (h.new_price - h.old_price) / h.old_price * 100
#                 ),
#                 "reason": h.reason
#             }
#             for h in history.scalars().all()
#         ]
        
#     async def get_price_trends(
#         self,
#         category_id: Optional[uuid.UUID] = None
#     ) -> Dict[str, Any]:
#         """Get price trends analysis"""
#         query = """
#         SELECT 
#             DATE(created_at) as date,
#             AVG(new_price - old_price) as avg_change,
#             COUNT(*) as changes_count,
#             SUM(CASE WHEN new_price > old_price THEN 1 ELSE 0 END) as increases,
#             SUM(CASE WHEN new_price < old_price THEN 1 ELSE 0 END) as decreases
#         FROM price_history ph
#         JOIN products p ON ph.product_id = p.id
#         WHERE ph.created_at >= NOW() - INTERVAL '30 days'
#         """
        
#         if category_id:
#             query += f" AND p.category_id = '{category_id}'"
            
#         query += " GROUP BY DATE(created_at) ORDER BY date"
        
#         result = await self.db.execute(query)
        
#         trends = []
#         for row in result:
#             trends.append({
#                 "date": row.date,
#                 "average_change": float(row.avg_change),
#                 "total_changes": row.changes_count,
#                 "price_increases": row.increases,
#                 "price_decreases": row.decreases
#             })
            
#         return {
#             "trends": trends,
#             "summary": self._calculate_trend_summary(trends)
#         }
        
#     async def _send_price_drop_alerts(
#         self,
#         product: Product,
#         history: PriceHistory
#     ) -> None:
#         """Send price drop alerts to users watching this product"""
#         # Get users who have this product in wishlist
#         from app.models import WishlistItem
        
#         wishlist_users = await self.db.execute(
#             select(WishlistItem.user_id)
#             .where(WishlistItem.product_id == product.id)
#         )
        
#         for user_id in wishlist_users.scalars().all():
#             await self.notification_service.send_price_drop_alert(
#                 user_id,
#                 product,
#                 history.old_price,
#                 history.new_price
#             )
            
#     def _calculate_trend_summary(self, trends: List[Dict]) -> Dict[str, Any]:
#         """Calculate summary statistics for trends"""
#         if not trends:
#             return {}
            
#         total_increases = sum(t["price_increases"] for t in trends)
#         total_decreases = sum(t["price_decreases"] for t in trends)
#         avg_daily_change = sum(t["average_change"] for t in trends) / len(trends)
        
#         return {
#             "total_price_increases": total_increases,
#             "total_price_decreases": total_decreases,
#             "average_daily_change": avg_daily_change,
#             "trend_direction": "increasing" if avg_daily_change > 0 else "decreasing"
#         }
