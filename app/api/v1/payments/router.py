"""
Payment API routes
"""

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from .schemas import (
    PaymentInitiate,
    PaymentVerify,
    PaymentResponse,
    PaymentInitiateResponse,
    RefundRequest,
    RefundResponse,
    PaymentWebhook,
    PaymentHistoryResponse,
    PaymentMethodResponse
)
from .services import PaymentService

router = APIRouter()

@router.get(
    "/methods",
    response_model=List[PaymentMethodResponse],
    summary="Get payment methods",
    description="Get available payment methods"
)
async def get_payment_methods(
    db: AsyncSession = Depends(get_db)
):
    """Get available payment methods"""
    service = PaymentService(db)
    methods = await service.get_payment_methods()
    return methods

@router.post(
    "/initiate",
    response_model=PaymentInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate payment",
    description="Initiate payment for an order"
)
async def initiate_payment(
    payment_data: PaymentInitiate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate payment"""
    service = PaymentService(db)
    result = await service.initiate_payment(
        user_id=uuid.UUID(current_user["id"]),
        data=payment_data
    )
    return PaymentInitiateResponse(**result)

@router.post(
    "/verify",
    response_model=PaymentResponse,
    summary="Verify payment",
    description="Verify payment after gateway response"
)
async def verify_payment(
    verification_data: PaymentVerify,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify payment"""
    service = PaymentService(db)
    payment = await service.verify_payment(
        user_id=uuid.UUID(current_user["id"]),
        data=verification_data
    )
    return PaymentResponse.from_orm(payment)

@router.get(
    "/history",
    response_model=PaymentHistoryResponse,
    summary="Get payment history",
    description="Get user's payment history"
)
async def get_payment_history(
    page: int = 1,
    size: int = 20,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get payment history"""
    from sqlalchemy import select, func
    from app.models import Payment, Order
    
    # Query payments for user's orders
    query = (
        select(Payment)
        .join(Order)
        .where(Order.buyer_id == uuid.UUID(current_user["id"]))
        .order_by(Payment.created_at.desc())
    )
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply pagination
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    
    # Execute query
    result = await db.execute(query)
    payments = result.scalars().all()
    
    # Calculate pages
    pages = (total + size - 1) // size
    
    return PaymentHistoryResponse(
        payments=[PaymentResponse.from_orm(p) for p in payments],
        total=total,
        page=page,
        size=size,
        pages=pages
    )

@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Get payment details",
    description="Get details of a specific payment"
)
async def get_payment(
    payment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get payment details"""
    from sqlalchemy import select
    from app.models import Payment, Order
    
    # Get payment with order
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.order))
        .where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise NotFoundException("Payment not found")
    
    # Verify ownership
    if payment.order.buyer_id != uuid.UUID(current_user["id"]):
        raise ForbiddenException("Access denied")
    
    return PaymentResponse.from_orm(payment)

@router.post(
    "/{payment_id}/refund",
    response_model=RefundResponse,
    summary="Request refund",
    description="Request refund for a payment"
)
async def request_refund(
    payment_id: uuid.UUID,
    refund_data: RefundRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Request payment refund"""
    # Get payment
    from sqlalchemy import select
    from app.models import Payment
    
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.order))
        .where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise NotFoundException("Payment not found")
    
    # Verify ownership
    if payment.order.buyer_id != uuid.UUID(current_user["id"]):
        raise ForbiddenException("Access denied")
    
    # Process refund
    service = PaymentService(db)
    refund = await service.process_refund(
        order=payment.order,
        amount=refund_data.amount,
        reason=refund_data.reason
    )
    
    return RefundResponse(**refund)

@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Payment webhook",
    description="Handle payment gateway webhooks"
)
async def payment_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Handle payment gateway webhook"""
    # Get request body
    body = await request.json()
    
    # Process webhook
    service = PaymentService(db)
    await service.handle_webhook(
        webhook_data=body,
        signature=x_razorpay_signature
    )
    
    return {"status": "ok"}
