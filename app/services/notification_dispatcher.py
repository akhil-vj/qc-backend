"""Central notification dispatcher"""

from typing import Optional, Dict, Any, List
from enum import Enum
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.notification import NotificationChannel
from app.services.email_service import EmailService
from app.services.sms_service import SMSService
from app.services.push_notification_service import PushNotificationService
from app.services.notification_websocket import WebSocketNotificationService
from app.core.cache import cache

logger = logging.getLogger(__name__)

class NotificationType(str, Enum):
    OTP = "otp"
    ORDER_CONFIRMATION = "order_confirmation"
    ORDER_UPDATE = "order_update"
    PROMOTIONAL = "promotional"
    ALERT = "alert"
    REMINDER = "reminder"

class NotificationDispatcher:
    """Central service for dispatching notifications"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService()
        self.sms_service = SMSService()
        self.push_service = PushNotificationService(db)
        self.websocket_service = WebSocketNotificationService()
        
    async def notify_user(
        self,
        user_id: str,
        notification_type: NotificationType,
        data: Dict[str, Any],
        channels: Optional[List[str]] = None,
        priority: str = "normal"
    ) -> Dict[str, bool]:
        """Send notification to user via available channels"""
        # Get user
        user = await self.db.get(User, user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            return {"success": False}
            
        # Determine channels to use
        if not channels:
            channels = await self._get_user_preferred_channels(user, notification_type)
            
        results = {}
        
        # Send via each channel
        for channel in channels:
            try:
                if channel == "email" and user.email:
                    results["email"] = await self._send_email_notification(
                        user, notification_type, data
                    )
                    
                elif channel == "sms" and user.phone:
                    results["sms"] = await self._send_sms_notification(
                        user, notification_type, data
                    )
                    
                elif channel == "push":
                    results["push"] = await self._send_push_notification(
                        user, notification_type, data, priority
                    )
                    
                elif channel == "websocket":
                    results["websocket"] = await self._send_websocket_notification(
                        user, notification_type, data, priority
                    )
                    
            except Exception as e:
                logger.error(f"Failed to send {channel} notification: {str(e)}")
                results[channel] = False
                
        # Store notification in database
        await self._store_notification(user_id, notification_type, data, results)
        
        return results
        
    async def _get_user_preferred_channels(
        self,
        user: User,
        notification_type: NotificationType
    ) -> List[str]:
        """Get user's preferred notification channels"""
        # Check user preferences
        preferences = user.notification_preferences or {}
        
        # Default channels by notification type
        defaults = {
            NotificationType.OTP: ["sms", "email"],
            NotificationType.ORDER_CONFIRMATION: ["email", "push", "websocket"],
            NotificationType.ORDER_UPDATE: ["push", "websocket", "sms"],
            NotificationType.PROMOTIONAL: ["push", "email"],
            NotificationType.ALERT: ["push", "websocket", "sms"],
            NotificationType.REMINDER: ["push", "email"]
        }
        
        # Use user preferences or defaults
        type_prefs = preferences.get(notification_type.value, {})
        if type_prefs.get("enabled", True):
            return type_prefs.get("channels", defaults.get(notification_type, ["push"]))
        
        return []
        
    async def _send_email_notification(
        self,
        user: User,
        notification_type: NotificationType,
        data: Dict[str, Any]
    ) -> bool:
        """Send email notification"""
        if notification_type == NotificationType.OTP:
            return await self.email_service.send_otp_email(
                user.email, data["otp"], user.name
            )
        elif notification_type == NotificationType.ORDER_CONFIRMATION:
            return await self.email_service.send_order_confirmation(
                user.email, data
            )
        # Add more notification types...
        
        return False
        
    async def _send_sms_notification(
        self,
        user: User,
        notification_type: NotificationType,
        data: Dict[str, Any]
    ) -> bool:
        """Send SMS notification"""
        if notification_type == NotificationType.OTP:
            return await self.sms_service.send_otp_sms(
                user.phone, data["otp"]
            )
        elif notification_type == NotificationType.ORDER_UPDATE:
            return await self.sms_service.send_order_update_sms(
                user.phone, data["order_number"], data["status"]
            )
        # Add more notification types...
        
        return False
        
    async def _send_push_notification(
        self,
        user: User,
        notification_type: NotificationType,
        data: Dict[str, Any],
        priority: str
    ) -> bool:
        """Send push notification"""
        # Implementation depends on push service
        return True
        
    async def _send_websocket_notification(
        self,
        user: User,
        notification_type: NotificationType,
        data: Dict[str, Any],
        priority: str
    ) -> bool:
        """Send WebSocket notification"""
        from app.core.websocket import manager
        
        notification = {
            "type": notification_type.value,
            "data": data,
            "priority": priority
        }
        
        await manager.send_notification(str(user.id), notification)
        return True
        
    async def _store_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        data: Dict[str, Any],
        results: Dict[str, bool]
    ):
        """Store notification in database"""
        from app.models.notification import Notification
        
        notification = Notification(
            user_id=user_id,
            type=notification_type.value,
            title=data.get("title", ""),
            message=data.get("message", ""),
            data=data,
            channels_attempted=list(results.keys()),
            channels_succeeded=[k for k, v in results.items() if v],
            is_read=False
        )
        
        self.db.add(notification)
        await self.db.commit()
