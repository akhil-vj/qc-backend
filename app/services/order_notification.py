"""Order notification service"""

from app.tasks.email_tasks import send_email_task
from app.tasks.sms_tasks import send_sms_task
from app.tasks.push_notification_tasks import send_order_notification_task
from app.core.websocket import manager

class OrderNotificationService:
    """Service for sending order-related notifications"""
    
    async def send_order_confirmation(self, order):
        """Send order confirmation via multiple channels"""
        # Email
        if order.buyer.email:
            send_email_task.delay(
                to_email=order.buyer.email,
                subject=f"Order Confirmed - #{order.order_number}",
                body=f"Your order #{order.order_number} has been confirmed.",
                html_body=self._generate_order_email_html(order)
            )
            
        # SMS
        if order.buyer.phone:
            send_sms_task.delay(
                to_number=order.buyer.phone,
                message=f"QuickCart: Order #{order.order_number} confirmed! "
                       f"Total: ₹{order.total_amount}. Track at app.quickcart.com/orders"
            )
            
        # Push notification
        send_order_notification_task.delay(
            order_id=str(order.id),
            notification_type="order_confirmed"
        )
        
        # WebSocket notification
        await manager.send_notification(str(order.buyer_id), {
            "title": "Order Confirmed!",
            "message": f"Your order #{order.order_number} has been confirmed",
            "type": "order_update",
            "data": {
                "order_id": str(order.id),
                "status": "confirmed"
            }
        })
        
        # Notify seller
        await manager.send_notification(str(order.seller_id), {
            "title": "New Order!",
            "message": f"You have a new order #{order.order_number}",
            "type": "new_order",
            "data": {
                "order_id": str(order.id)
            }
        })
        
    async def send_refund_notification(self, order, refund_amount):
        """Send refund notification"""
        # Email
        if order.buyer.email:
            send_email_task.delay(
                to_email=order.buyer.email,
                subject=f"Refund Processed - Order #{order.order_number}",
                body=f"Your refund of ₹{refund_amount} has been processed.",
                html_body=f"""
                <h2>Refund Processed</h2>
                <p>Your refund for order #{order.order_number} has been processed.</p>
                <p><strong>Refund Amount:</strong> ₹{refund_amount}</p>
                <p>The amount will be credited to your original payment method within 5-7 business days.</p>
                """
            )
            
        # SMS
        if order.buyer.phone:
            send_sms_task.delay(
                to_number=order.buyer.phone,
                message=f"QuickCart: Refund of ₹{refund_amount} processed for "
                       f"order #{order.order_number}. Credits in 5-7 days."
            )
            
    def _generate_order_email_html(self, order):
        """Generate order confirmation email HTML"""
        items_html = ""
        for item in order.items:
            items_html += f"""
            <tr>
                <td>{item.product.title}</td>
                <td>{item.quantity}</td>
                <td>₹{item.price}</td>
                <td>₹{item.quantity * item.price}</td>
            </tr>
            """
            
        return f"""
        <h2>Order Confirmation</h2>
        <p>Thank you for your order!</p>
        
        <h3>Order Details</h3>
        <p><strong>Order Number:</strong> {order.order_number}</p>
        <p><strong>Order Date:</strong> {order.created_at.strftime('%B %d, %Y')}</p>
        
        <h3>Items</h3>
        <table border="1" cellpadding="5">
            <tr>
                <th>Product</th>
                <th>Quantity</th>
                <th>Price</th>
                <th>Total</th>
            </tr>
            {items_html}
        </table>
        
        <h3>Order Summary</h3>
        <p><strong>Subtotal:</strong> ₹{order.subtotal}</p>
        <p><strong>Delivery Fee:</strong> ₹{order.delivery_fee}</p>
        <p><strong>Discount:</strong> -₹{order.discount_amount}</p>
        <p><strong>Total:</strong> ₹{order.total_amount}</p>
        
        <h3>Delivery Address</h3>
        <p>{order.shipping_address.full_address}</p>
        
        <p>You can track your order <a href="https://app.quickcart.com/orders/{order.id}">here</a>.</p>
        """
