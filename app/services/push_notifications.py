"""Push notification service with FCM"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import asyncio
import uuid

from app.core.config import settings
from app.models import User, DeviceToken, NotificationLog

# Initialize Firebase Admin SDK
cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred)

class PushNotificationService:
    """Service for managing push notifications"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def register_device_token(
        self,
        user_id: str,
        token: str,
        device_type: str,
        device_info: Optional[Dict[str, Any]] = None
    ):
        """Register or update device token"""
        # Check if token exists
        existing = await self.db.execute(
            select(DeviceToken).where(DeviceToken.token == token)
        )
        device_token = existing.scalar()
        
        if device_token:
            # Update existing
            device_token.user_id = user_id
            device_token.last_used = datetime.utcnow()
            device_token.is_active = True
        else:
            # Create new
            device_token = DeviceToken(
                user_id=user_id,
                token=token,
                device_type=device_type,
                device_info=device_info or {}
            )
            self.db.add(device_token)
            
        await self.db.commit()
        
    async def send_to_user(
        self,
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None,
        action_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send notification to specific user"""
        # Get active tokens for user
        tokens = await self._get_user_tokens(user_id)
        
        if not tokens:
            return {"success": False, "error": "No active tokens"}
            
        # Create message
        message_data = data or {}
        if action_url:
            message_data["action_url"] = action_url
            
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url
        )
        
        # Send to all user's devices
        results = []
        for token in tokens:
            try:
                message = messaging.Message(
                    notification=notification,
                    data=message_data,
                    token=token.token,
                    android=messaging.AndroidConfig(
                        priority='high',
                        notification=messaging.AndroidNotification(
                            click_action="FLUTTER_NOTIFICATION_CLICK",
                            sound="default"
                        )
                    ),
                    apns=messaging.APNSConfig(
                        payload=messaging.APNSPayload(
                            aps=messaging.Aps(
                                sound="default",
                                badge=1
                            )
                        )
                    )
                )
                
                response = messaging.send(message)
                results.append({"token": token.token, "success": True, "message_id": response})
                
                # Log successful send
                await self._log_notification(
                    user_id=user_id,
                    title=title,
                    body=body,
                    status="sent",
                    message_id=response
                )
                
            except Exception as e:
                results.append({"token": token.token, "success": False, "error": str(e)})
                
                # Mark token as invalid if error indicates
                if "registration-token-not-registered" in str(e):
                    await self._invalidate_token(token.token)
                    
        await self.db.commit()
        
        success_count = sum(1 for r in results if r["success"])
        return {
            "success": success_count > 0,
            "sent_count": success_count,
            "failed_count": len(results) - success_count,
            "results": results
        }
        
    async def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send notification to topic subscribers"""
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url
        )
        
        message = messaging.Message(
            notification=notification,
            data=data or {},
            topic=topic
        )
        
        try:
            response = messaging.send(message)
            
            # Log broadcast
            await self._log_notification(
                title=title,
                body=body,
                status="sent",
                message_id=response,
                topic=topic
            )
            
            return {"success": True, "message_id": response}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def send_broadcast(
        self,
        title: str,
        body: str,
        user_filters: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send broadcast notification to multiple users"""
        # Get target users
        query = select(User.id).where(User.is_active == True)
        
        if user_filters:
            if user_filters.get("role"):
                query = query.where(User.role == user_filters["role"])
            if user_filters.get("has_purchase"):
                query = query.join(Order).where(Order.status == "delivered").distinct()
                
        users = await self.db.execute(query)
        user_ids = [str(uid) for uid in users.scalars().all()]
        
        # Send notifications in batches
        batch_size = 500
        total_sent = 0
        total_failed = 0
        
        for i in range(0, len(user_ids), batch_size):
            batch_ids = user_ids[i:i + batch_size]
            
            # Get tokens for batch
            tokens = await self.db.execute(
                select(DeviceToken)
                .where(
                    and_(
                        DeviceToken.user_id.in_(batch_ids),
                        DeviceToken.is_active == True
                    )
                )
            )
            
            registration_tokens = [t.token for t in tokens.scalars().all()]
            
            if registration_tokens:
                # Create multicast message
                message = messaging.MulticastMessage(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                        image=image_url
                    ),
                    data=data or {},
                    tokens=registration_tokens
                )
                
                try:
                    response = messaging.send_multicast(message)
                    total_sent += response.success_count
                    total_failed += response.failure_count
                    
                    # Handle failed tokens
                    if response.failure_count > 0:
                        for idx, resp in enumerate(response.responses):
                            if not resp.success and resp.exception:
                                if "registration-token-not-registered" in str(resp.exception):
                                    await self._invalidate_token(registration_tokens[idx])
                                    
                except Exception as e:
                    total_failed += len(registration_tokens)
                    
        # Log broadcast
        await self._log_notification(
            title=title,
            body=body,
            status="broadcast",
            metadata={
                "total_users": len(user_ids),
                "sent_count": total_sent,
                "failed_count": total_failed
            }
        )
        
        await self.db.commit()
        
        return {
            "success": total_sent > 0,
            "total_users": len(user_ids),
            "sent_count": total_sent,
            "failed_count": total_failed
        }
        
    async def subscribe_to_topic(self, user_id: str, topic: str):
        """Subscribe user to a topic"""
        tokens = await self._get_user_tokens(user_id)
        
        if not tokens:
            return {"success": False, "error": "No active tokens"}
            
        registration_tokens = [t.token for t in tokens]
        
        try:
            response = messaging.subscribe_to_topic(registration_tokens, topic)
            
            # Update user's topic subscriptions
            user = await self.db.get(User, user_id)
            if user:
                topics = user.notification_topics or []
                if topic not in topics:
                    topics.append(topic)
                    user.notification_topics = topics
                    await self.db.commit()
                    
            return {
                "success": True,
                "success_count": response.success_count,
                "failure_count": response.failure_count
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def unsubscribe_from_topic(self, user_id: str, topic: str):
        """Unsubscribe user from a topic"""
        tokens = await self._get_user_tokens(user_id)
        
        if not tokens:
            return {"success": False, "error": "No active tokens"}
            
        registration_tokens = [t.token for t in tokens]
        
        try:
            response = messaging.unsubscribe_from_topic(registration_tokens, topic)
            
            # Update user's topic subscriptions
            user = await self.db.get(User, user_id)
            if user and user.notification_topics:
                topics = user.notification_topics
                if topic in topics:
                    topics.remove(topic)
                    user.notification_topics = topics
                    await self.db.commit()
                    
            return {
                "success": True,
                "success_count": response.success_count,
                "failure_count": response.failure_count
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    async def send_order_update(
        self,
        order_id: str,
        status: str,
        custom_message: Optional[str] = None
    ):
        """Send order status update notification"""
        from app.models import Order
        
        order = await self.db.get(Order, order_id)
        if not order:
            return
            
        # Prepare notification content
        status_messages = {
            "confirmed": "Your order has been confirmed!",
            "processing": "Your order is being processed.",
            "shipped": "Your order has been shipped!",
            "out_for_delivery": "Your order is out for delivery!",
            "delivered": "Your order has been delivered!",
            "cancelled": "Your order has been cancelled."
        }
        
        title = f"Order Update - {order.order_number}"
        body = custom_message or status_messages.get(status, f"Order status: {status}")
        
        await self.send_to_user(
            user_id=str(order.buyer_id),
            title=title,
            body=body,
            data={
                "type": "order_update",
                "order_id": str(order_id),
                "status": status
            },
            action_url=f"/orders/{order_id}"
        )
        
    async def send_flash_sale_notification(
        self,
        sale_id: str,
        title: str,
        description: str,
        image_url: Optional[str] = None
    ):
        """Send flash sale notification to all users"""
        await self.send_to_topic(
            topic="flash_sales",
            title=title,
            body=description,
            data={
                "type": "flash_sale",
                "sale_id": sale_id
            },
            image_url=image_url
        )
        
    async def _get_user_tokens(self, user_id: str) -> List[DeviceToken]:
        """Get active device tokens for user"""
        result = await self.db.execute(
            select(DeviceToken)
            .where(
                and_(
                    DeviceToken.user_id == user_id,
                    DeviceToken.is_active == True
                )
            )
        )
        return result.scalars().all()
        
    async def _invalidate_token(self, token: str):
        """Mark token as inactive"""
        await self.db.execute(
            update(DeviceToken)
            .where(DeviceToken.token == token)
            .values(is_active=False)
        )
        
    async def _log_notification(
        self,
        title: str,
        body: str,
        status: str,
        user_id: Optional[str] = None,
        message_id: Optional[str] = None,
        topic: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log notification for analytics"""
        log = NotificationLog(
            user_id=user_id,
            title=title,
            body=body,
            status=status,
            message_id=message_id,
            topic=topic,
            metadata=metadata or {}
        )
        self.db.add(log)
