"""Complete email background tasks"""

from celery import Task
from celery.utils.log import get_task_logger
from typing import Dict, Any, List
import asyncio

from app.core.celery_app import celery_app
from app.services.email_service import EmailService
from app.core.database import get_db_sync

logger = get_task_logger(__name__)

class EmailTask(Task):
    """Base email task with retry logic"""
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

@celery_app.task(base=EmailTask, name="send_order_confirmation_email")
def send_order_confirmation_email(order_id: str):
    """Send order confirmation email"""
    try:
        db = next(get_db_sync())
        
        # Get order details
        from app.models.order import Order
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order or not order.buyer.email:
            return {"success": False, "error": "Order not found or no email"}
            
        # Prepare order data
        order_data = {
            "id": str(order.id),
            "order_number": order.order_number,
            "created_at": order.created_at,
            "total_amount": float(order.total_amount),
            "subtotal": float(order.subtotal),
            "delivery_fee": float(order.delivery_fee),
            "discount_amount": float(order.discount_amount),
            "items": [
                {
                    "product_name": item.product.title,
                    "quantity": item.quantity,
                    "price": float(item.price),
                    "total": float(item.total_amount),
                    "image": item.product.primary_image
                }
                for item in order.items
            ],
            "shipping_address": {
                "name": order.shipping_address.full_name,
                "address": order.shipping_address.full_address,
                "phone": order.shipping_address.phone
            },
            "payment_method": order.payment_method
        }
        
        # Send email
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        email_service = EmailService()
        result = loop.run_until_complete(
            email_service.send_order_confirmation(
                to_email=order.buyer.email,
                order_data=order_data
            )
        )
        
        loop.close()
        
        logger.info(f"Order confirmation email sent for order {order_id}")
        
        return {"success": result}
        
    except Exception as e:
        logger.error(f"Error sending order confirmation: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="send_abandoned_cart_reminders")
def send_abandoned_cart_reminders():
    """Send abandoned cart reminder emails"""
    try:
        db = next(get_db_sync())
        
        # Find abandoned carts (items added >2 hours ago, no order)
        from datetime import datetime, timedelta
        from app.models.cart import CartItem
        from app.models.user import User
        
        cutoff_time = datetime.utcnow() - timedelta(hours=2)
        reminder_sent_after = datetime.utcnow() - timedelta(days=1)
        
        abandoned_carts = db.query(User).join(CartItem).filter(
            CartItem.created_at < cutoff_time,
            CartItem.saved_for_later == False,
            User.email.isnot(None),
            or_(
                User.last_cart_reminder_at.is_(None),
                User.last_cart_reminder_at < reminder_sent_after
            )
        ).distinct().all()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        email_service = EmailService()
        sent_count = 0
        
        for user in abandoned_carts:
            # Get cart items
            cart_items = db.query(CartItem).filter(
                CartItem.user_id == user.id,
                CartItem.saved_for_later == False
            ).all()
            
            if not cart_items:
                continue
                
            # Prepare cart data
            cart_data = [
                {
                    "product_name": item.product.title,
                    "quantity": item.quantity,
                    "price": float(item.product.price),
                    "image": item.product.primary_image
                }
                for item in cart_items
            ]
            
            cart_total = sum(item.product.price * item.quantity for item in cart_items)
            
            # Generate discount code
            discount_code = f"SAVE10{user.id[:4].upper()}"
            
            # Send reminder
            result = loop.run_until_complete(
                email_service.send_abandoned_cart_reminder(
                    to_email=user.email,
                    user_name=user.name,
                    cart_items=cart_data,
                    cart_total=float(cart_total),
                    discount_code=discount_code
                )
            )
            
            if result:
                sent_count += 1
                user.last_cart_reminder_at = datetime.utcnow()
                
        db.commit()
        loop.close()
        
        logger.info(f"Sent {sent_count} abandoned cart reminders")
        
        return {"reminders_sent": sent_count}
        
    except Exception as e:
        logger.error(f"Error sending abandoned cart reminders: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="send_review_request_email")
def send_review_request_email(order_id: str):
    """Send review request email after delivery"""
    try:
        db = next(get_db_sync())
        
        from app.models.order import Order
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order or not order.buyer.email:
            return {"success": False}
            
        # Check if already reviewed
        from app.models.review import Review
        existing_reviews = db.query(Review).filter(
            Review.user_id == order.buyer_id,
            Review.product_id.in_([item.product_id for item in order.items])
        ).count()
        
        if existing_reviews >= len(order.items):
            return {"success": False, "reason": "Already reviewed"}
            
        # Send review request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        email_service = EmailService()
        
        template_data = {
            "user_name": order.buyer.name,
            "order_number": order.order_number,
            "products": [
                {
                    "id": str(item.product_id),
                    "name": item.product.title,
                    "image": item.product.primary_image,
                    "review_url": f"{settings.FRONTEND_URL}/products/{item.product.slug}/review"
                }
                for item in order.items
            ],
            "incentive": "Earn 50 coins for each review!"
        }
        
        result = loop.run_until_complete(
            email_service.send_email(
                to_email=order.buyer.email,
                subject="How was your order? Share your feedback!",
                body="We'd love to hear about your experience.",
                html_body=email_service.env.get_template("review_request.html").render(**template_data)
            )
        )
        
        loop.close()
        
        return {"success": result}
        
    except Exception as e:
        logger.error(f"Error sending review request: {str(e)}")
        raise
    finally:
        db.close()


# """Email-related Celery tasks"""

# from celery import Task
# from celery.utils.log import get_task_logger
# from typing import Dict, Any, List
# import asyncio

# from app.core.celery_app import celery_app
# from app.services.email_service import EmailService
# from app.core.database import get_db_sync

# logger = get_task_logger(__name__)

# class EmailTask(Task):
#     """Base class for email tasks with retry logic"""
    
#     autoretry_for = (Exception,)
#     retry_kwargs = {"max_retries": 3}
#     retry_backoff = True
#     retry_backoff_max = 600  # 10 minutes
#     retry_jitter = True

@celery_app.task(base=EmailTask, name="send_email")
def send_email_task(
    to_email: str,
    subject: str,
    body: str,
    html_body: str = None,
    attachments: List[Dict[str, Any]] = None
) -> bool:
    """Send email task"""
    try:
        logger.info(f"Sending email to {to_email}")
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        email_service = EmailService()
        result = loop.run_until_complete(
            email_service.send_email(
                to_email=to_email,
                subject=subject,
                body=body,
                html_body=html_body,
                attachments=attachments
            )
        )
        
        loop.close()
        
        if result:
            logger.info(f"Email sent successfully to {to_email}")
        else:
            logger.error(f"Failed to send email to {to_email}")
            
        return result
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        raise

# @celery_app.task(name="send_bulk_emails")
# def send_bulk_emails_task(
#     email_list: List[Dict[str, Any]],
#     batch_size: int = 50
# ) -> Dict[str, int]:
#     """Send bulk emails with batching"""
#     sent_count = 0
#     failed_count = 0
    
#     for i in range(0, len(email_list), batch_size):
#         batch = email_list[i:i + batch_size]
        
#         for email_data in batch:
#             try:
#                 send_email_task.apply_async(
#                     args=[
#                         email_data["to_email"],
#                         email_data["subject"],
#                         email_data["body"],
#                         email_data.get("html_body")
#                     ],
#                     countdown=i * 0.1  # Slight delay between emails
#                 )
#                 sent_count += 1
#             except Exception as e:
#                 logger.error(f"Failed to queue email: {str(e)}")
#                 failed_count += 1
                
#     return {
#         "sent": sent_count,
#         "failed": failed_count
#     }

# @celery_app.task(name="send_abandoned_cart_reminders")
# def send_abandoned_cart_reminders():
#     """Send abandoned cart reminder emails"""
#     from app.services.abandoned_cart import AbandonedCartService
    
#     try:
#         db = next(get_db_sync())
#         service = AbandonedCartService(db)
        
#         # Get abandoned carts
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
        
#         result = loop.run_until_complete(
#             service.send_recovery_campaign("email")
#         )
        
#         loop.close()
        
#         logger.info(f"Sent {result['messages_sent']} abandoned cart reminders")
        
#         return result
        
#     except Exception as e:
#         logger.error(f"Error sending abandoned cart reminders: {str(e)}")
#         raise
#     finally:
#         db.close()
