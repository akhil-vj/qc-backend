"""Push notification service implementation"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from firebase_admin import messaging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
import logging

from app.models.push_notification import DeviceToken, PushNotificationLog
from app.models.user import User
from app.core.firebase import firebase_app

logger = logging.getLogger(__name__)

class PushNotificationService:
    """Service for handling push notifications via FCM"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def register_device_token(
        self,
        user_id: str,
        token: str,
        device_type: str,
        device_info: Optional[Dict[str, str]] = None
    ) -> DeviceToken:
        """Register or update a device token"""
        # Check if token already exists
        stmt = select(DeviceToken).where(DeviceToken.token == token)
        result = await self.db.execute(stmt)
        existing_token = result.scalar_one_or_none()
        
        if existing_token:
            # Update existing token
            existing_token.user_id = user_id
            existing_token.is_active = True
            existing_token.last_used_at = datetime.utcnow()
            if device_info:
                existing_token.device_name = device_info.get("device_name")
                existing_token.device_model = device_info.get("device_model")
                existing_token.app_version = device_info.get("app_version")
        else:
            # Create new token
            device_token = DeviceToken(
                user_id=user_id,
                token=token,
                device_type=device_type,
                device_name=device_info.get("device_name") if device_info else None,
                device_model=device_info.get("device_model") if device_info else None,
                app_version=device_info.get("app_version") if device_info else None,
                last_used_at=datetime.utcnow()
            )
            self.db.add(device_token)
            
        await self.db.commit()
        return existing_token or device_token
        
    async def unregister_device_token(self, token: str, user_id: Optional[str] = None):
        """Unregister a device token"""
        stmt = update(DeviceToken).where(DeviceToken.token == token)
        if user_id:
            stmt = stmt.where(DeviceToken.user_id == user_id)
        stmt = stmt.values(is_active=False)
        
        await self.db.execute(stmt)
        await self.db.commit()
        
    async def send_to_user(
        self,
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None,
        action_url: Optional[str] = None,
        notification_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send notification to all active devices of a user"""
        # Get all active tokens for user
        stmt = select(DeviceToken).where(
            and_(
                DeviceToken.user_id == user_id,
                DeviceToken.is_active == True
            )
        )
        result = await self.db.execute(stmt)
        device_tokens = result.scalars().all()
        
        if not device_tokens:
            return {"success": False, "error": "No active device tokens found"}
            
        # Create notification log
        notification_log = PushNotificationLog(
            user_id=user_id,
            title=title,
            body=body,
            data=data,
            image_url=image_url,
            action_url=action_url,
            notification_type=notification_type
        )
        self.db.add(notification_log)
        await self.db.flush()
        
        # Prepare FCM message
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url
        )
        
        # Add action URL to data if provided
        message_data = data or {}
        if action_url:
            message_data["action_url"] = action_url
            
        # Send to all devices
        success_count = 0
        failed_tokens = []
        
        for device_token in device_tokens:
            try:
                message = messaging.Message(
                    notification=notification,
                    data=message_data,
                    token=device_token.token,
                    android=messaging.AndroidConfig(
                        priority='high',
                        notification=messaging.AndroidNotification(
                            click_action='FLUTTER_NOTIFICATION_CLICK',
                            sound='default'
                        )
                    ),
                    apns=messaging.APNSConfig(
                        payload=messaging.APNSPayload(
                            aps=messaging.Aps(
                                badge=1,
                                sound='default'
                            )
                        )
                    )
                )
                
                # Send message
                response = messaging.send(message)
                success_count += 1
                
                # Update last used
                device_token.last_used_at = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Failed to send notification to token {device_token.token}: {str(e)}")
                failed_tokens.append(device_token.token)
                
                # Mark token as inactive if it's invalid
                if 'registration-token-not-registered' in str(e):
                    device_token.is_active = False
                    
        # Update notification log
        if success_count > 0:
            notification_log.status = "sent"
            notification_log.sent_at = datetime.utcnow()
        else:
            notification_log.status = "failed"
            notification_log.error_message = f"Failed to send to all devices"
            
        await self.db.commit()
        
        return {
            "success": success_count > 0,
            "sent_count": success_count,
            "failed_count": len(failed_tokens),
            "notification_id": str(notification_log.id)
        }
        
    async def send_order_notification(
        self,
        order_id: str,
        user_id: str,
        title: str,
        body: str
    ):
        """Send order-related notification"""
        return await self.send_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data={"order_id": order_id, "type": "order"},
            action_url=f"/orders/{order_id}",
            notification_type="order_update"
        )
        
    async def send_flash_sale_notification(
        self,
        user_ids: List[str],
        sale_title: str,
        sale_description: str,
        sale_id: str,
        image_url: Optional[str] = None
    ):
        """Send flash sale notification to multiple users"""
        results = []
        
        for user_id in user_ids:
            result = await self.send_to_user(
                user_id=user_id,
                title=f"🔥 Flash Sale: {sale_title}",
                body=sale_description,
                data={"sale_id": sale_id, "type": "flash_sale"},
                image_url=image_url,
                action_url=f"/flash-sales/{sale_id}",
                notification_type="flash_sale"
            )
            results.append(result)
            
        return results
        
    async def send_bulk_notification(
        self,
        user_ids: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        notification_type: Optional[str] = None
    ):
        """Send notification to multiple users"""
        results = []
        
        for user_id in user_ids:
            result = await self.send_to_user(
                user_id=user_id,
                title=title,
                body=body,
                data=data,
                notification_type=notification_type
            )
            results.append(result)
            
        success_count = sum(1 for r in results if r.get("success"))
        
        return {
            "total_users": len(user_ids),
            "success_count": success_count,
            "failed_count": len(user_ids) - success_count
        }
