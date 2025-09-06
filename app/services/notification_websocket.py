"""WebSocket notification service"""

from typing import List, Dict, Any
from app.core.websocket import manager
from app.models.notification import Notification
from app.core.database import AsyncSession

class WebSocketNotificationService:
    """Service for sending notifications via WebSocket"""
    
    async def send_order_update(self, order_id: str, buyer_id: str, status: str):
        """Send order status update"""
        notification = {
            "title": "Order Update",
            "message": f"Your order status changed to {status}",
            "type": "order_update",
            "data": {
                "order_id": order_id,
                "status": status
            }
        }
        
        await manager.send_notification(buyer_id, notification)
        
    async def send_new_order_notification(self, order_id: str, seller_id: str, order_number: str):
        """Notify seller of new order"""
        notification = {
            "title": "New Order!",
            "message": f"You have a new order #{order_number}",
            "type": "new_order",
            "data": {
                "order_id": order_id,
                "order_number": order_number
            },
            "priority": "high"
        }
        
        await manager.send_notification(seller_id, notification)
        
    async def send_flash_sale_notification(self, sale_data: Dict[str, Any], user_ids: List[str]):
        """Send flash sale notification to multiple users"""
        notification = {
            "title": "🔥 Flash Sale Alert!",
            "message": sale_data["title"],
            "type": "flash_sale",
            "data": {
                "sale_id": sale_data["id"],
                "title": sale_data["title"],
                "discount": sale_data["discount"],
                "ends_at": sale_data["ends_at"]
            },
            "priority": "high"
        }
        
        await manager.broadcast_notification(user_ids, notification)
        
    async def send_admin_message(self, user_id: str, message: str, action_url: Optional[str] = None):
        """Send admin message to user"""
        notification = {
            "title": "Message from Admin",
            "message": message,
            "type": "admin_message",
            "data": {
                "action_url": action_url
            },
            "priority": "high"
        }
        
        await manager.send_notification(user_id, notification)
