"""Complete order service with state machine"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from app.models.order import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.models.cart import CartItem
from app.models.inventory import inventory_manager

class OrderStateMachine:
    """Order state machine for status transitions"""
    
    TRANSITIONS = {
        OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
        OrderStatus.CONFIRMED: [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
        OrderStatus.PROCESSING: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
        OrderStatus.SHIPPED: [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED, OrderStatus.RETURNED],
        OrderStatus.OUT_FOR_DELIVERY: [OrderStatus.DELIVERED, OrderStatus.FAILED],
        OrderStatus.DELIVERED: [OrderStatus.RETURN_REQUESTED],
        OrderStatus.RETURN_REQUESTED: [OrderStatus.RETURN_APPROVED, OrderStatus.RETURN_REJECTED],
        OrderStatus.RETURN_APPROVED: [OrderStatus.RETURN_PICKED, OrderStatus.CANCELLED],
        OrderStatus.RETURN_PICKED: [OrderStatus.REFUNDED],
        OrderStatus.FAILED: [OrderStatus.SHIPPED, OrderStatus.CANCELLED]
    }
    
    @classmethod
    def can_transition(cls, from_status: OrderStatus, to_status: OrderStatus) -> bool:
        """Check if transition is valid"""
        return to_status in cls.TRANSITIONS.get(from_status, [])
        
    @classmethod
    def get_available_transitions(cls, current_status: OrderStatus) -> List[OrderStatus]:
        """Get available transitions from current status"""
        return cls.TRANSITIONS.get(current_status, [])

class OrderService:
    """Complete order service with business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.state_machine = OrderStateMachine()
        
    async def create_order(
        self,
        buyer_id: str,
        order_data: Dict[str, Any]
    ) -> Order:
        """Create order from cart"""
        # Get cart items
        cart_items = await self.db.execute(
            select(CartItem)
            .where(CartItem.user_id == buyer_id)
            .where(CartItem.saved_for_later == False)
        )
        cart_items = cart_items.scalars().all()
        
        if not cart_items:
            raise ValueError("Cart is empty")
            
        # Validate inventory
        for item in cart_items:
            available = await inventory_manager.check_availability(
                self.db,
                item.product_id,
                item.quantity
            )
            if not available:
                raise ValueError(f"Product {item.product.title} is out of stock")
                
        # Calculate totals
        subtotal = sum(item.product.price * item.quantity for item in cart_items)
        delivery_fee = self._calculate_delivery_fee(subtotal)
        discount_amount = order_data.get("discount_amount", 0)
        total_amount = subtotal + delivery_fee - discount_amount
        
        # Create order
        order = Order(
            buyer_id=buyer_id,
            seller_id=cart_items[0].product.seller_id,  # Single seller for now
            order_number=await self._generate_order_number(),
            status=OrderStatus.PENDING,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            discount_amount=discount_amount,
            total_amount=total_amount,
            payment_method=order_data["payment_method"],
            shipping_address_id=order_data["shipping_address_id"],
            billing_address_id=order_data.get("billing_address_id", order_data["shipping_address_id"]),
            notes=order_data.get("notes"),
            metadata=order_data.get("metadata", {})
        )
        
        self.db.add(order)
        await self.db.flush()
        
        # Create order items and reserve inventory
        for cart_item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=cart_item.product_id,
                variant_id=cart_item.variant_id,
                quantity=cart_item.quantity,
                price=cart_item.product.price,
                discount_amount=0,  # Item-level discount if any
                total_amount=cart_item.product.price * cart_item.quantity
            )
            self.db.add(order_item)
            
            # Reserve inventory
            await inventory_manager.reserve_stock(
                self.db,
                cart_item.product_id,
                cart_item.quantity,
                order.id
            )
            
        # Create initial status history
        status_history = OrderStatusHistory(
            order_id=order.id,
            status=OrderStatus.PENDING,
            notes="Order created",
            created_by=buyer_id
        )
        self.db.add(status_history)
        
        # Clear cart
        for item in cart_items:
            await self.db.delete(item)
            
        await self.db.commit()
        await self.db.refresh(order)
        
        return order
        
    async def update_order_status(
        self,
        order_id: str,
        new_status: str,
        tracking_info: Optional[Dict[str, Any]] = None,
        updated_by: str = None
    ) -> Order:
        """Update order status with state machine validation"""
        order = await self.db.get(Order, order_id)
        if not order:
            raise ValueError("Order not found")
            
        # Validate transition
        current_status = order.status
        new_status_enum = OrderStatus(new_status)
        
        if not self.state_machine.can_transition(current_status, new_status_enum):
            raise ValueError(
                f"Invalid status transition from {current_status.value} to {new_status}"
            )
            
        # Update status
        order.status = new_status_enum
        
        # Handle status-specific logic
        if new_status_enum == OrderStatus.CONFIRMED:
            order.confirmed_at = datetime.utcnow()
            # Confirm inventory reservation
            await inventory_manager.confirm_reservation(self.db, order.id)
            
        elif new_status_enum == OrderStatus.SHIPPED:
            order.shipped_at = datetime.utcnow()
            if tracking_info:
                order.tracking_number = tracking_info.get("tracking_number")
                order.carrier = tracking_info.get("carrier")
                order.estimated_delivery = tracking_info.get("estimated_delivery")
                
        elif new_status_enum == OrderStatus.DELIVERED:
            order.delivered_at = datetime.utcnow()
            # Complete inventory transaction
            await inventory_manager.complete_order(self.db, order.id)
            
        elif new_status_enum == OrderStatus.CANCELLED:
            order.cancelled_at = datetime.utcnow()
            order.cancellation_reason = tracking_info.get("reason") if tracking_info else None
            # Release inventory
            await inventory_manager.cancel_reservation(self.db, order.id)
            
        # Add status history
        status_history = OrderStatusHistory(
            order_id=order.id,
            status=new_status_enum,
            notes=tracking_info.get("notes") if tracking_info else None,
            metadata=tracking_info,
            created_by=updated_by
        )
        self.db.add(status_history)
        
        await self.db.commit()
        await self.db.refresh(order)
        
        return order
        
    async def process_refund(
        self,
        order_id: str,
        refund_amount: float,
        reason: str,
        processed_by: str
    ) -> Dict[str, Any]:
        """Process order refund"""
        order = await self.db.get(Order, order_id)
        if not order:
            raise ValueError("Order not found")
            
        # Validate refund amount
        if refund_amount > float(order.total_amount):
            raise ValueError("Refund amount exceeds order total")
            
        # Create refund record
        from app.models.payment import Refund, RefundStatus
        
        refund = Refund(
            order_id=order.id,
            amount=Decimal(str(refund_amount)),
            reason=reason,
            status=RefundStatus.PENDING,
            processed_by=processed_by
        )
        
        self.db.add(refund)
        
        # Update order status
        await self.update_order_status(
            order_id=order_id,
            new_status=OrderStatus.REFUNDED.value,
            tracking_info={"refund_id": str(refund.id)},
            updated_by=processed_by
        )
        
        # Process payment refund
        from app.services.payment_service import PaymentService
        payment_service = PaymentService(self.db)
        
        payment_result = await payment_service.process_refund(
            order_id=order_id,
            amount=refund_amount
        )
        
        if payment_result["success"]:
            refund.status = RefundStatus.COMPLETED
            refund.payment_reference = payment_result["reference_id"]
            refund.completed_at = datetime.utcnow()
        else:
            refund.status = RefundStatus.FAILED
            refund.failure_reason = payment_result.get("error")
            
        await self.db.commit()
        
        return {
            "refund_id": str(refund.id),
            "status": refund.status.value,
            "amount": float(refund.amount),
            "payment_reference": refund.payment_reference
        }
        
    async def _generate_order_number(self) -> str:
        """Generate unique order number"""
        # Format: QC-YYYYMMDD-XXXXX
        today = datetime.utcnow().strftime("%Y%m%d")
        
        # Get today's order count
        count = await self.db.scalar(
            select(func.count(Order.id)).where(
                Order.created_at >= datetime.utcnow().date()
            )
        )
        
        return f"QC-{today}-{count + 1:05d}"
        
    def _calculate_delivery_fee(self, subtotal: Decimal) -> Decimal:
        """Calculate delivery fee based on order value"""
        if subtotal >= 500:
            return Decimal("0")
        elif subtotal >= 200:
            return Decimal("30")
        else:
            return Decimal("50")
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_orders(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Order]:
        """Get orders for a user"""
        result = await self.db.execute(
            select(Order)
            .where(Order.buyer_id == user_id)
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_seller_orders(
        self, 
        seller_id: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Order]:
        """Get orders for a seller"""
        result = await self.db.execute(
            select(Order)
            .where(Order.seller_id == seller_id)
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def search_orders(
        self,
        search_params: Dict[str, Any],
        skip: int = 0,
        limit: int = 100
    ) -> List[Order]:
        """Search orders with filters"""
        query = select(Order)
        
        if search_params.get("order_number"):
            query = query.where(Order.order_number.ilike(f"%{search_params['order_number']}%"))
        
        if search_params.get("status"):
            query = query.where(Order.status == OrderStatus(search_params["status"]))
        
        if search_params.get("buyer_id"):
            query = query.where(Order.buyer_id == search_params["buyer_id"])
        
        if search_params.get("seller_id"):
            query = query.where(Order.seller_id == search_params["seller_id"])
        
        if search_params.get("date_from"):
            query = query.where(Order.created_at >= search_params["date_from"])
        
        if search_params.get("date_to"):
            query = query.where(Order.created_at <= search_params["date_to"])
        
        query = query.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
