"""Abandoned cart recovery service"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models import CartItem, User, Product
from app.services.email import EmailService
from app.services.notification import NotificationService
from app.core.cache import cache

class AbandonedCartService:
    """Service for recovering abandoned carts"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService()
        self.notification_service = NotificationService(db)
        
    async def identify_abandoned_carts(
        self,
        hours_threshold: int = 24
    ) -> List[Dict[str, Any]]:
        """Identify carts abandoned for specified hours"""
        threshold_time = datetime.utcnow() - timedelta(hours=hours_threshold)
        
        # Get carts not updated recently
        abandoned_carts = await self.db.execute(
            select(
                CartItem.user_id,
                func.count(CartItem.id).label("item_count"),
                func.sum(CartItem.price * CartItem.quantity).label("cart_value"),
                func.max(CartItem.updated_at).label("last_activity")
            )
            .where(
                and_(
                    CartItem.user_id.isnot(None),
                    CartItem.saved_for_later == False,
                    CartItem.updated_at < threshold_time
                )
            )
            .group_by(CartItem.user_id)
        )
        
        results = []
        for cart in abandoned_carts:
            # Check if user has placed order after cart abandonment
            recent_order = await self.db.execute(
                select(Order.id)
                .where(
                    and_(
                        Order.buyer_id == cart.user_id,
                        Order.created_at > cart.last_activity
                    )
                )
                .limit(1)
            )
            
            if not recent_order.scalar():
                results.append({
                    "user_id": cart.user_id,
                    "item_count": cart.item_count,
                    "cart_value": cart.cart_value,
                    "abandoned_at": cart.last_activity,
                    "hours_abandoned": int(
                        (datetime.utcnow() - cart.last_activity).total_seconds() / 3600
                    )
                })
                
        return results
        
    async def send_recovery_campaign(
        self,
        campaign_type: str = "email"
    ) -> Dict[str, Any]:
        """Send abandoned cart recovery campaign"""
        abandoned_carts = await self.identify_abandoned_carts()
        
        sent_count = 0
        for cart_data in abandoned_carts:
            # Check if already sent recently
            sent_key = f"cart_recovery:{cart_data['user_id']}"
            if await cache.exists(sent_key):
                continue
                
            # Get user details
            user = await self.db.get(User, cart_data["user_id"])
            
            if campaign_type == "email" and user.email:
                await self._send_recovery_email(user, cart_data)
                sent_count += 1
            elif campaign_type == "notification":
                await self._send_recovery_notification(user, cart_data)
                sent_count += 1
                
            # Mark as sent (don't spam for 48 hours)
            await cache.set(sent_key, True, expire=timedelta(hours=48))
            
        return {
            "carts_identified": len(abandoned_carts),
            "messages_sent": sent_count,
            "campaign_type": campaign_type
        }
        
    async def _send_recovery_email(
        self,
        user: User,
        cart_data: Dict[str, Any]
    ) -> None:
        """Send recovery email with personalized content"""
        # Get cart items for email
        cart_items = await self.db.execute(
            select(CartItem)
            .options(selectinload(CartItem.product))
            .where(
                and_(
                    CartItem.user_id == user.id,
                    CartItem.saved_for_later == False
                )
            )
        )
        
        items = []
        for item in cart_items.scalars().all():
            items.append({
                "name": item.product.title,
                "price": item.price,
                "quantity": item.quantity,
                "image": item.product.thumbnail
            })
            
        # Send email
        await self.email_service.send_abandoned_cart_email(
            user.email,
            user.name,
            items,
            cart_data["cart_value"],
            recovery_url=f"https://quickcart.com/cart?recovery={user.id}"
        )
        
    async def _send_recovery_notification(
        self,
        user: User,
        cart_data: Dict[str, Any]
    ) -> None:
        """Send push notification for cart recovery"""
        await self.notification_service.create_notification(
            user_id=user.id,
            title="You have items in your cart!",
            message=f"Complete your purchase of {cart_data['item_count']} items worth ₹{cart_data['cart_value']}",
            type="cart_abandoned",
            action_url="/cart"
        )
