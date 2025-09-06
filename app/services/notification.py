"""
Notification service for sending various notifications
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Order, Payment, Notification
from app.services.email import EmailService
from app.services.sms import SMSService

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for managing notifications"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService()
        self.sms_service = SMSService()
    
    async def create_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        type: str,
        action_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """Create in-app notification"""
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            action_url=action_url,
            metadata=metadata or {}
        )
        
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        
        return notification
    
    async def send_order_created(self, order: Order) -> None:
        """Send notifications for order creation"""
        # Get user details
        from sqlalchemy import select
        
        buyer_result = await self.db.execute(
            select(User).where(User.id == order.buyer_id)
        )
        buyer = buyer_result.scalar_one()
        
        seller_result = await self.db.execute(
            select(User).where(User.id == order.seller_id)
        )
        seller = seller_result.scalar_one()
        
        # Create tasks for parallel execution
        tasks = []
        
        # In-app notifications
        tasks.append(self.create_notification(
            user_id=str(order.buyer_id),
            title="Order Placed Successfully",
            message=f"Your order #{order.order_number} has been placed",
            type="order",
            action_url=f"/orders/{order.id}"
        ))
        
        tasks.append(self.create_notification(
            user_id=str(order.seller_id),
            title="New Order Received",
            message=f"You have a new order #{order.order_number}",
            type="order",
            action_url=f"/seller/orders/{order.id}"
        ))
        
        # Email notifications
        if buyer.email:
            tasks.append(self.email_service.send_order_confirmation(
                user_email=buyer.email,
                order_number=order.order_number,
                total_amount=str(order.total_amount)
            ))
        
        # SMS notifications
        tasks.append(self.sms_service.send_order_update(
            phone=buyer.phone,
            order_number=order.order_number,
            status="confirmed"
        ))
        
        # Execute all tasks
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_order_status_update(self, order: Order) -> None:
        """Send notifications for order status update"""
        # Get buyer
        from sqlalchemy import select
        
        result = await self.db.execute(
            select(User).where(User.id == order.buyer_id)
        )
        buyer = result.scalar_one()
        
        status_messages = {
            "confirmed": "Your order has been confirmed",
            "processing": "Your order is being processed",
            "shipped": "Your order has been shipped",
            "delivered": "Your order has been delivered",
            "cancelled": "Your order has been cancelled"
        }
        
        message = status_messages.get(
            order.status.value,
            f"Your order status is now {order.status.value}"
        )
        
        tasks = []
        
        # In-app notification
        tasks.append(self.create_notification(
            user_id=str(order.buyer_id),
            title=f"Order #{order.order_number} Update",
            message=message,
            type="order",
            action_url=f"/orders/{order.id}"
        ))
        
        # SMS notification
        tasks.append(self.sms_service.send_order_update(
            phone=buyer.phone,
            order_number=order.order_number,
            status=order.status.value
        ))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_payment_success(self, payment: Payment) -> None:
        """Send payment success notification"""
        # Get order and user
        await self.db.refresh(payment, ["order"])
        order = payment.order
        
        from sqlalchemy import select
        result = await self.db.execute(
            select(User).where(User.id == order.buyer_id)
        )
        buyer = result.scalar_one()
        
        # Create notification
        await self.create_notification(
            user_id=str(order.buyer_id),
            title="Payment Successful",
            message=f"Payment of ₹{payment.amount} for order #{order.order_number} completed",
            type="payment",
            action_url=f"/orders/{order.id}"
        )
    
    async def send_payment_failed(self, payment: Payment) -> None:
        """Send payment failure notification"""
        # Get order
        await self.db.refresh(payment, ["order"])
        order = payment.order
        
        # Create notification
        await self.create_notification(
            user_id=str(order.buyer_id),
            title="Payment Failed",
            message=f"Payment for order #{order.order_number} failed. Please try again.",
            type="payment",
            action_url=f"/orders/{order.id}"
        )
