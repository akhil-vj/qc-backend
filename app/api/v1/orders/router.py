"""
Order API routes
"""

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
import logging
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user, require_seller
from app.models.order import OrderStatus, Order

logger = logging.getLogger(__name__)
from .schemas import (
    OrderCreate,
    OrderUpdate,
    OrderResponse,
    OrderListResponse,
    OrderCancelRequest,
    OrderReturnRequest,
    OrderTrackingResponse,
    OrderInvoiceRequest,
    OrderSummaryResponse
)
from .services import OrderService

router = APIRouter()

@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create order",
    description="Create a new order from cart or direct items"
)
async def create_order(
    order_data: OrderCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new order"""
    service = OrderService(db)
    order = await service.create_order(
        buyer_id=uuid.UUID(current_user["id"]),
        data=order_data
    )
    return OrderResponse.from_orm(order)

@router.get(
    "/",
    response_model=OrderListResponse,
    summary="List orders",
    description="Get paginated list of orders"
)
async def list_orders(
    status: Optional[OrderStatus] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user orders"""
    service = OrderService(db)
    result = await service.list_orders(
        user_id=uuid.UUID(current_user["id"]),
        role=current_user["role"],
        status=status,
        page=page,
        size=size
    )
    return OrderListResponse(**result)

@router.get(
    "/summary",
    response_model=OrderSummaryResponse,
    summary="Get order summary",
    description="Get order statistics and summary"
)
async def get_order_summary(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get order summary statistics"""
    service = OrderService(db)
    summary = await service.get_order_summary(
        user_id=uuid.UUID(current_user["id"]),
        role=current_user["role"]
    )
    return OrderSummaryResponse(**summary)

@router.get(
    "/track/{order_number}",
    response_model=OrderTrackingResponse,
    summary="Track order",
    description="Get order tracking information by order number"
)
async def track_order(
    order_number: str,
    db: AsyncSession = Depends(get_db)
):
    """Track order by order number"""
    service = OrderService(db)
    tracking = await service.get_order_tracking(order_number)
    return OrderTrackingResponse(**tracking)

@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order details",
    description="Get detailed information about a specific order"
)
async def get_order(
    order_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get order details"""
    service = OrderService(db)
    order = await service.get_order(
        order_id=order_id,
        user_id=uuid.UUID(current_user["id"])
    )
    return OrderResponse.from_orm(order)

@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status",
    description="Update order status (Seller only)"
)
async def update_order_status(
    order_id: uuid.UUID,
    status_update: OrderUpdate,
    current_user: dict = Depends(require_seller),
    db: AsyncSession = Depends(get_db)
):
    """Update order status"""
    service = OrderService(db)
    order = await service.update_order_status(
        order_id=order_id,
        seller_id=uuid.UUID(current_user["id"]),
        new_status=status_update.status
    )
    return OrderResponse.from_orm(order)

@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Cancel order",
    description="Cancel an order"
)
async def cancel_order(
    order_id: uuid.UUID,
    cancel_request: OrderCancelRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel order"""
    service = OrderService(db)
    order = await service.cancel_order(
        order_id=order_id,
        user_id=uuid.UUID(current_user["id"]),
        reason=cancel_request.reason
    )
    return OrderResponse.from_orm(order)

@router.post(
    "/{order_id}/return",
    response_model=dict,
    summary="Return order",
    description="Initiate order return"
)
async def return_order(
    order_id: uuid.UUID,
    return_request: OrderReturnRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate order return"""
    try:
        # Get order and verify ownership
        order = await db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        if order.buyer_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to return this order")
        
        # Check if order is eligible for return
        if order.status not in ["delivered", "completed"]:
            raise HTTPException(status_code=400, detail="Order not eligible for return")
        
        # Create return record
        from app.models.order import OrderReturn
        return_record = OrderReturn(
            order_id=order_id,
            user_id=current_user["id"],
            reason=return_request.reason,
            description=return_request.description,
            return_items=return_request.items,
            status="pending",
            requested_at=datetime.utcnow()
        )
        
        db.add(return_record)
        await db.commit()
        await db.refresh(return_record)
        
        # Update order status
        order.status = "return_requested"
        await db.commit()
        
        # Send notification to seller
        # from app.services.notification_service import NotificationService
        # notification_service = NotificationService(db)
        # await notification_service.send_notification(
        #     user_id=order.seller_id,
        #     title="Return Request",
        #     message=f"Return requested for order #{order.order_number}",
        #     notification_type="order_return"
        # )
        
        return {
            "return_id": str(return_record.id),
            "status": "pending",
            "message": "Return request submitted successfully"
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Return order error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process return request")

@router.post(
    "/{order_id}/invoice",
    response_model=dict,
    summary="Generate invoice",
    description="Generate order invoice"
)
async def generate_invoice(
    order_id: uuid.UUID,
    invoice_request: OrderInvoiceRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate order invoice"""
    try:
        # Get order and verify access
        order = await db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Check if user has access (buyer or seller)
        if order.buyer_id != current_user["id"] and order.seller_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to access this order")
        
        # Check if order is completed
        if order.status not in ["delivered", "completed"]:
            raise HTTPException(status_code=400, detail="Invoice can only be generated for completed orders")
        
        # Generate invoice data
        invoice_data = {
            "invoice_id": f"INV-{order.order_number}-{datetime.utcnow().strftime('%Y%m%d')}",
            "order_id": str(order_id),
            "order_number": order.order_number,
            "invoice_date": datetime.utcnow().isoformat(),
            "due_date": datetime.utcnow().isoformat(),
            "status": "paid",
            "customer": {
                "name": order.billing_address.get("name", "Customer"),
                "email": order.billing_address.get("email", ""),
                "address": order.billing_address
            },
            "items": order.items,
            "subtotal": float(order.subtotal),
            "tax_amount": float(order.tax_amount),
            "shipping_cost": float(order.shipping_cost),
            "discount_amount": float(order.discount_amount) if order.discount_amount else 0,
            "total_amount": float(order.total_amount),
            "payment_method": order.payment_method,
            "payment_status": "completed"
        }
        
        # In a real implementation, you would:
        # 1. Generate PDF invoice using libraries like reportlab or weasyprint
        # 2. Store invoice in database
        # 3. Send via email if requested
        # 4. Upload to cloud storage
        
        # For now, return invoice data
        return {
            "invoice": invoice_data,
            "download_url": f"/api/v1/orders/{order_id}/invoice/download",
            "message": "Invoice generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Invoice generation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate invoice")
