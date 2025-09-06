"""Push notification Celery tasks"""

from celery import Task
from celery.utils.log import get_task_logger
from typing import List, Dict, Any, Optional

from app.core.celery_app import celery_app
from app.services.firebase_service import FirebaseService
from app.core.database import get_db_sync

logger = get_task_logger(__name__)

class PushNotificationTask(Task):
    """Base task for push notifications"""
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    
    _firebase_service = None
    
    @property
    def firebase_service(self):
        if self._firebase_service is None:
            self._firebase_service = FirebaseService()
        return self._firebase_service

@celery_app.task(base=PushNotificationTask, name="send_push_notification")
def send_push_notification_task(
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
    image_url: Optional[str] = None,
    priority: str = "high"
):
    """Send push notification to user"""
    try:
        db = next(get_db_sync())
        
        # Get user's device tokens
        from app.models.device_token import DeviceToken
        tokens = db.query(DeviceToken).filter(
            DeviceToken.user_id == user_id,
            DeviceToken.is_active == True
        ).all()
        
        if not tokens:
            logger.warning(f"No active device tokens for user {user_id}")
            return {"success": False, "reason": "No device tokens"}
            
        firebase_service = send_push_notification_task.firebase_service
        
        # Send to all user's devices
        success_count = 0
        for token in tokens:
            result = firebase_service.send_notification(
                token=token.token,
                title=title,
                body=body,
                data=data,
                image_url=image_url,
                priority=priority
            )
            
            if result:
                success_count += 1
            else:
                # Mark token as inactive
                token.is_active = False
                
        db.commit()
        
        return {
            "success": success_count > 0,
            "devices_notified": success_count,
            "total_devices": len(tokens)
        }
        
    except Exception as e:
        logger.error(f"Error sending push notification: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="send_order_notification")
def send_order_notification_task(order_id: str, notification_type: str):
    """Send order-related push notifications"""
    try:
        db = next(get_db_sync())
        
        from app.models.order import Order
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            logger.error(f"Order {order_id} not found")
            return
            
        # Determine recipient and message
        if notification_type == "order_confirmed":
            user_id = order.buyer_id
            title = "Order Confirmed! 🎉"
            body = f"Your order #{order.order_number} has been confirmed"
            data = {
                "type": "order_update",
                "order_id": str(order.id),
                "status": "confirmed"
            }
            
        elif notification_type == "new_order":
            user_id = order.seller_id
            title = "New Order! 📦"
            body = f"You have a new order #{order.order_number}"
            data = {
                "type": "new_order",
                "order_id": str(order.id)
            }
            
        elif notification_type == "order_shipped":
            user_id = order.buyer_id
            title = "Order Shipped! 🚚"
            body = f"Your order #{order.order_number} is on its way"
            data = {
                "type": "order_update",
                "order_id": str(order.id),
                "status": "shipped",
                "tracking_number": order.tracking_number
            }
            
        elif notification_type == "order_delivered":
            user_id = order.buyer_id
            title = "Order Delivered! ✅"
            body = f"Your order #{order.order_number} has been delivered"
            data = {
                "type": "order_update",
                "order_id": str(order.id),
                "status": "delivered"
            }
        else:
            logger.error(f"Unknown notification type: {notification_type}")
            return
            
        # Send notification
        send_push_notification_task.delay(
            user_id=str(user_id),
            title=title,
            body=body,
            data=data
        )
        
    except Exception as e:
        logger.error(f"Error sending order notification: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="send_inventory_alert")
def send_inventory_alert_task(product_id: str, current_stock: int):
    """Send low inventory alert to seller"""
    try:
        db = next(get_db_sync())
        
        from app.models.product import Product
        product = db.query(Product).filter(Product.id == product_id).first()
        
        if not product:
            return
            
        # Send notification to seller
        send_push_notification_task.delay(
            user_id=str(product.seller_id),
            title="Low Inventory Alert! ⚠️",
            body=f"{product.title} has only {current_stock} units left",
            data={
                "type": "inventory_alert",
                "product_id": str(product.id),
                "current_stock": str(current_stock)
            },
            priority="high"
        )
        
    except Exception as e:
        logger.error(f"Error sending inventory alert: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="send_flash_sale_notification")
def send_flash_sale_notification_task(
    sale_id: str,
    title: str,
    description: str,
    target_users: Optional[List[str]] = None
):
    """Send flash sale notifications"""
    try:
        firebase_service = FirebaseService()
        
        notification_data = {
            "type": "flash_sale",
            "sale_id": sale_id
        }
        
        if target_users:
            # Send to specific users
            for user_id in target_users:
                send_push_notification_task.delay(
                    user_id=user_id,
                    title=f"🔥 {title}",
                    body=description,
                    data=notification_data,
                    priority="high"
                )
        else:
            # Send to topic (all users subscribed to deals)
            firebase_service.send_topic_notification(
                topic="flash_sales",
                title=f"🔥 {title}",
                body=description,
                data=notification_data
            )
            
    except Exception as e:
        logger.error(f"Error sending flash sale notification: {str(e)}")
        raise
