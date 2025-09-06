"""
Order service layer
Handles order processing and management
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
import uuid
import random
import string

from app.models import (
    Order, OrderItem, OrderStatus, Product, User, CartItem,
    Payment, PaymentStatus, Coupon, CouponUsage, Address
)
from app.core.exceptions import (
    NotFoundException, BadRequestException, ForbiddenException,
    InsufficientStockException, OrderNotCancellableException
)
from app.core.cache import cache, invalidate_cache
from app.api.v1.cart.services import CartService
from app.api.v1.payments.services import PaymentService
from app.services.notification import NotificationService
from .schemas import OrderCreate, OrderUpdate
from .state_machine import OrderStateMachine

class OrderService:
    """Order service for business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cart_service = CartService(db)
        self.payment_service = PaymentService(db)
        self.notification_service = NotificationService(db)
        self.state_machine = OrderStateMachine()
    
    def generate_order_number(self) -> str:
        """Generate unique order number"""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"ORD{timestamp}{random_suffix}"
    
    async def create_order(
        self,
        buyer_id: uuid.UUID,
        data: OrderCreate
    ) -> Order:
        """
        Create new order from cart or direct items
        
        Args:
            buyer_id: Buyer user ID
            data: Order creation data
            
        Returns:
            Created order
            
        Raises:
            BadRequestException: If validation fails
            InsufficientStockException: If stock not available
        """
        # Group items by seller
        seller_items = {}
        total_amount = Decimal("0")
        
        for item in data.items:
            # Get product
            result = await self.db.execute(
                select(Product)
                .where(Product.id == item.product_id)
            )
            product = result.scalar_one_or_none()
            
            if not product or product.status != "active":
                raise NotFoundException(f"Product {item.product_id} not found or inactive")
            
            # Check stock
            if product.track_inventory and product.stock < item.quantity:
                raise InsufficientStockException(product.title, product.stock)
            
            # Group by seller
            seller_id = str(product.seller_id)
            if seller_id not in seller_items:
                seller_items[seller_id] = []
            
            seller_items[seller_id].append({
                "product": product,
                "quantity": item.quantity,
                "variant_id": item.variant_id
            })
        
        # Create order for each seller
        created_orders = []
        
        for seller_id, items in seller_items.items():
            # Calculate order totals
            subtotal = Decimal("0")
            order_items_data = []
            
            for item_data in items:
                product = item_data["product"]
                quantity = item_data["quantity"]
                
                # Calculate item total
                unit_price = product.final_price
                item_total = unit_price * quantity
                subtotal += item_total
                
                # Prepare order item data
                order_items_data.append({
                    "product_id": product.id,
                    "variant_id": item_data["variant_id"],
                    "product_name": product.title,
                    "product_sku": product.sku,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": item_total,
                    "discount_amount": Decimal("0"),  # Applied at order level
                    "tax_amount": Decimal("0")  # Calculated below
                })
                
                # Reduce stock
                if product.track_inventory:
                    product.stock -= quantity
                    product.purchase_count += 1
                    self.db.add(product)
            
            # Apply coupon if provided
            discount_amount = Decimal("0")
            if data.coupon_code:
                # Validate and apply coupon
                # This is simplified - in production, check usage limits, validity, etc.
                result = await self.db.execute(
                    select(Coupon)
                    .where(Coupon.code == data.coupon_code.upper())
                )
                coupon = result.scalar_one_or_none()
                
                if coupon and coupon.is_valid:
                    if coupon.discount_type == "percentage":
                        discount_amount = subtotal * (coupon.discount_value / 100)
                    else:
                        discount_amount = coupon.discount_value
                    
                    if coupon.max_discount:
                        discount_amount = min(discount_amount, coupon.max_discount)
            
            # Calculate tax (18% GST)
            tax_amount = (subtotal - discount_amount) * Decimal("0.18")
            
            # Calculate shipping
            shipping_fee = Decimal("0") if subtotal >= 500 else Decimal("40")
            
            # Total amount
            total_amount = subtotal - discount_amount + tax_amount + shipping_fee
            
            # Create order
            order = Order(
                order_number=self.generate_order_number(),
                buyer_id=buyer_id,
                seller_id=uuid.UUID(seller_id),
                subtotal=subtotal,
                tax_amount=tax_amount,
                shipping_fee=shipping_fee,
                discount_amount=discount_amount,
                total_amount=total_amount,
                status=OrderStatus.PENDING,
                payment_status="pending",
                shipping_address=data.shipping_address.dict(),
                billing_address=data.billing_address.dict() if data.billing_address else data.shipping_address.dict(),
                notes=data.notes
            )
            
            # Add order items
            for item_data in order_items_data:
                order_item = OrderItem(**item_data, order_id=order.id)
                self.db.add(order_item)
            
            self.db.add(order)
            created_orders.append(order)
        
        # Clear user's cart if ordering from cart
        await self.cart_service.clear_cart(user_id=buyer_id, session_id=None)
        
        # Commit all changes
        await self.db.commit()
        
        # Refresh orders
        for order in created_orders:
            await self.db.refresh(order)
        
        # Send notifications
        for order in created_orders:
            await self.notification_service.send_order_created(order)
        
        # Return first order (for single seller scenario)
        return created_orders[0]
    
    async def get_order(
        self,
        order_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None
    ) -> Order:
        """
        Get order details
        
        Args:
            order_id: Order ID
            user_id: Optional user ID for access control
            
        Returns:
            Order with related data
            
        Raises:
            NotFoundException: If order not found
            ForbiddenException: If user doesn't have access
        """
        # Get order with related data
        result = await self.db.execute(
            select(Order)
            .options(
                selectinload(Order.buyer),
                selectinload(Order.seller),
                selectinload(Order.items),
                selectinload(Order.payment)
            )
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise NotFoundException("Order not found")
        
        # Check access
        if user_id and order.buyer_id != user_id and order.seller_id != user_id:
            raise ForbiddenException("You don't have access to this order")
        
        # Add computed fields
        order.can_cancel = self.state_machine.can_transition(
            order.status, OrderStatus.CANCELLED
        )
        order.can_return = (
            order.status == OrderStatus.DELIVERED and
            order.delivered_at and
            datetime.utcnow() - order.delivered_at < timedelta(days=7)
        )
        
        return order
    
    async def list_orders(
        self,
        user_id: uuid.UUID,
        role: str,
        status: Optional[OrderStatus] = None,
        page: int = 1,
        size: int = 20
    ) -> Dict[str, Any]:
        """
        List orders for user
        
        Args:
            user_id: User ID
            role: User role (buyer/seller)
            status: Optional status filter
            page: Page number
            size: Page size
            
        Returns:
            Paginated order list
        """
        # Base query
        query = select(Order)
        
        # Apply role filter
        if role == "buyer":
            query = query.where(Order.buyer_id == user_id)
        elif role == "seller":
            query = query.where(Order.seller_id == user_id)
        else:
            # Admin can see all orders
            pass
        
        # Apply status filter
        if status:
            query = query.where(Order.status == status)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)
        
        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size).order_by(Order.created_at.desc())
        
        # Execute query
        result = await self.db.execute(
            query.options(
                selectinload(Order.buyer),
                selectinload(Order.seller),
                selectinload(Order.items)
            )
        )
        orders = result.scalars().all()
        
        # Calculate total pages
        total_pages = (total + size - 1) // size
        
        return {
            "items": orders,
            "total": total,
            "page": page,
            "size": size,
            "pages": total_pages
        }
    
    async def update_order_status(
        self,
        order_id: uuid.UUID,
        seller_id: uuid.UUID,
        new_status: OrderStatus
    ) -> Order:
        """
        Update order status
        
        Args:
            order_id: Order ID
            seller_id: Seller user ID
            new_status: New status
            
        Returns:
            Updated order
            
        Raises:
            NotFoundException: If order not found
            ForbiddenException: If not the seller
            BadRequestException: If transition not allowed
        """
        # Get order
        order = await self.get_order(order_id)
        
        if order.seller_id != seller_id:
            raise ForbiddenException("You can only update your own orders")
        
        # Validate state transition
        if not self.state_machine.can_transition(order.status, new_status):
            raise BadRequestException(
                f"Cannot transition from {order.status} to {new_status}"
            )
        
        # Update status
        order.status = new_status
        
        # Update timestamps based on status
        if new_status == OrderStatus.SHIPPED:
            order.expected_delivery = date.today() + timedelta(days=3)
        elif new_status == OrderStatus.DELIVERED:
            order.delivered_at = datetime.utcnow()
            order.payment_status = "completed"
        
        self.db.add(order)
        await self.db.commit()
        await self.db.refresh(order)
        
        # Send notifications
        await self.notification_service.send_order_status_update(order)
        
        return order
    
    async def cancel_order(
        self,
        order_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str
    ) -> Order:
        """
        Cancel order
        
        Args:
            order_id: Order ID
            user_id: User ID (buyer or seller)
            reason: Cancellation reason
            
        Returns:
            Cancelled order
            
        Raises:
            OrderNotCancellableException: If order cannot be cancelled
        """
        # Get order
        order = await self.get_order(order_id, user_id)
        
        # Check if cancellable
        if not self.state_machine.can_transition(order.status, OrderStatus.CANCELLED):
            raise OrderNotCancellableException()
        
        # Update status
        order.status = OrderStatus.CANCELLED
        order.notes = f"Cancellation reason: {reason}\n{order.notes or ''}"
        
        # Restore product stock
        for item in order.items:
            result = await self.db.execute(
                select(Product).where(Product.id == item.product_id)
            )
            product = result.scalar_one()
            
            if product.track_inventory:
                product.stock += item.quantity
                self.db.add(product)
        
        # Process refund if payment was made
        if order.payment_status == "completed":
            await self.payment_service.process_refund(order)
            order.status = OrderStatus.REFUNDED
        
        self.db.add(order)
        await self.db.commit()
        await self.db.refresh(order)
        
        # Send notifications
        await self.notification_service.send_order_cancelled(order)
        
        return order
    
    async def get_order_tracking(
        self,
        order_number: str
    ) -> Dict[str, Any]:
        """
        Get order tracking information
        
        Args:
            order_number: Order number
            
        Returns:
            Tracking information
        """
        # Get order
        result = await self.db.execute(
            select(Order).where(Order.order_number == order_number)
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise NotFoundException("Order not found")
        
        # Get tracking events (simplified)
        events = [
            {
                "status": "Order Placed",
                "timestamp": order.created_at,
                "description": "Your order has been placed successfully"
            }
        ]
        
        if order.status in [OrderStatus.CONFIRMED, OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
            events.append({
                "status": "Order Confirmed",
                "timestamp": order.created_at + timedelta(minutes=30),
                "description": "Your order has been confirmed"
            })
        
        if order.status in [OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
            events.append({
                "status": "Processing",
                "timestamp": order.created_at + timedelta(hours=2),
                "description": "Your order is being processed"
            })
        
        if order.status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
            events.append({
                "status": "Shipped",
                "timestamp": order.created_at + timedelta(days=1),
                "description": f"Your order has been shipped via {order.courier_partner or 'Partner'}"
            })
        
        if order.status == OrderStatus.DELIVERED:
            events.append({
                "status": "Delivered",
                "timestamp": order.delivered_at,
                "description": "Your order has been delivered"
            })
        
        return {
            "order_number": order.order_number,
            "status": order.status,
            "tracking_number": order.tracking_number,
            "courier_partner": order.courier_partner,
            "expected_delivery": order.expected_delivery,
            "events": events
        }
    
    async def get_order_summary(
        self,
        user_id: uuid.UUID,
        role: str
    ) -> Dict[str, Any]:
        """
        Get order summary statistics
        
        Args:
            user_id: User ID
            role: User role
            
        Returns:
            Order statistics
        """
        # Base conditions
        if role == "buyer":
            conditions = [Order.buyer_id == user_id]
        elif role == "seller":
            conditions = [Order.seller_id == user_id]
        else:
            conditions = []
        
        # Get statistics
        result = await self.db.execute(
            select(
                func.count(Order.id).label("total_orders"),
                func.count(Order.id).filter(Order.status == OrderStatus.PENDING).label("pending_orders"),
                func.count(Order.id).filter(Order.status == OrderStatus.DELIVERED).label("completed_orders"),
                func.count(Order.id).filter(Order.status == OrderStatus.CANCELLED).label("cancelled_orders"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_spent"),
                func.coalesce(func.sum(Order.discount_amount), 0).label("total_saved"),
                func.coalesce(func.avg(Order.total_amount), 0).label("average_order_value")
            )
            .where(*conditions)
        )
        
        stats = result.one()
        
        return {
            "total_orders": stats.total_orders,
            "pending_orders": stats.pending_orders,
            "completed_orders": stats.completed_orders,
            "cancelled_orders": stats.cancelled_orders,
            "total_spent": Decimal(str(stats.total_spent)),
            "total_saved": Decimal(str(stats.total_saved)),
            "average_order_value": Decimal(str(stats.average_order_value))
        }
