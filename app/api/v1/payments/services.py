"""
Payment service layer
Handles payment processing and integration
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid
import logging

from app.models import Order, Payment, PaymentStatus, PaymentMethod, User
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    InvalidPaymentException
)
from app.core.config import settings
from app.services.notification import NotificationService
from .razorpay_client import RazorpayClient
from .schemas import PaymentInitiate, PaymentVerify

logger = logging.getLogger(__name__)

class PaymentService:
    """Payment service for processing transactions"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.razorpay = RazorpayClient()
        self.notification_service = NotificationService(db)
    
    async def initiate_payment(
        self,
        user_id: uuid.UUID,
        data: PaymentInitiate
    ) -> Dict[str, Any]:
        """
        Initiate payment for order
        
        Args:
            user_id: User ID
            data: Payment initiation data
            
        Returns:
            Payment initiation response
            
        Raises:
            NotFoundException: If order not found
            BadRequestException: If order already paid
        """
        # Get order
        result = await self.db.execute(
            select(Order)
            .where(and_(
                Order.id == data.order_id,
                Order.buyer_id == user_id
            ))
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise NotFoundException("Order not found")
        
        if order.payment_status == "completed":
            raise BadRequestException("Order already paid")
        
        # Check for existing payment
        existing = await self.db.execute(
            select(Payment)
            .where(Payment.order_id == data.order_id)
        )
        payment = existing.scalar_one_or_none()
        
        if payment and payment.status == PaymentStatus.COMPLETED:
            raise BadRequestException("Payment already completed")
        
        # Create or update payment record
        if not payment:
            payment = Payment(
                order_id=data.order_id,
                amount=order.total_amount,
                currency="INR",
                payment_method=data.payment_method,
                status=PaymentStatus.PENDING
            )
            self.db.add(payment)
        
        # Handle different payment methods
        if data.payment_method == PaymentMethod.COD:
            # Cash on delivery - no gateway needed
            payment.status = PaymentStatus.PENDING
            order.payment_status = "cod"
            order.status = OrderStatus.CONFIRMED
            
            self.db.add(order)
            await self.db.commit()
            
            return {
                "payment_id": payment.id,
                "gateway_order_id": None,
                "amount": payment.amount,
                "currency": payment.currency,
                "options": {
                    "method": "cod",
                    "message": "Order placed with Cash on Delivery"
                }
            }
        
        elif data.payment_method in [PaymentMethod.RAZORPAY, PaymentMethod.CARD, PaymentMethod.UPI, PaymentMethod.NET_BANKING]:
            # Create Razorpay order
            razorpay_order = self.razorpay.create_order(
                amount=int(order.total_amount * 100),  # Convert to paise
                currency="INR",
                receipt=order.order_number
            )
            
            # Update payment record
            payment.gateway_order_id = razorpay_order["id"]
            payment.gateway_response = razorpay_order
            
            await self.db.commit()
            await self.db.refresh(payment)
            
            # Get user details for prefill
            user_result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one()
            
            return {
                "payment_id": payment.id,
                "gateway_order_id": razorpay_order["id"],
                "amount": payment.amount,
                "currency": payment.currency,
                "key_id": settings.RAZORPAY_KEY_ID,
                "options": {
                    "name": "QuickCart",
                    "description": f"Payment for Order #{order.order_number}",
                    "order_id": razorpay_order["id"],
                    "prefill": {
                        "name": user.name or "",
                        "email": user.email or "",
                        "contact": user.phone
                    },
                    "theme": {
                        "color": "#3B82F6"
                    }
                }
            }
        
        else:
            raise BadRequestException(f"Payment method {data.payment_method} not supported")
    
    async def verify_payment(
        self,
        user_id: uuid.UUID,
        data: PaymentVerify
    ) -> Payment:
        """
        Verify payment from gateway
        
        Args:
            user_id: User ID
            data: Payment verification data
            
        Returns:
            Verified payment
            
        Raises:
            InvalidPaymentException: If payment verification fails
        """
        # Get payment
        result = await self.db.execute(
            select(Payment)
            .options(selectinload(Payment.order))
            .where(Payment.order_id == data.order_id)
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise NotFoundException("Payment not found")
        
        # Verify ownership
        if payment.order.buyer_id != user_id:
            raise BadRequestException("Unauthorized")
        
        # Verify with Razorpay
        try:
            is_valid = self.razorpay.verify_payment_signature(
                order_id=payment.gateway_order_id,
                payment_id=data.payment_id,
                signature=data.payment_signature
            )
            
            if not is_valid:
                raise InvalidPaymentException("Payment signature verification failed")
            
            # Update payment
            payment.gateway_payment_id = data.payment_id
            payment.gateway_signature = data.payment_signature
            payment.status = PaymentStatus.COMPLETED
            
            # Update order
            payment.order.payment_status = "completed"
            payment.order.status = OrderStatus.CONFIRMED
            
            # Fetch payment details from Razorpay
            payment_details = self.razorpay.fetch_payment(data.payment_id)
            payment.gateway_response = payment_details
            
            self.db.add(payment)
            self.db.add(payment.order)
            await self.db.commit()
            await self.db.refresh(payment)
            
            # Send notifications
            await self.notification_service.send_payment_success(payment)
            
            return payment
            
        except Exception as e:
            logger.error(f"Payment verification failed: {str(e)}")
            
            # Mark payment as failed
            payment.status = PaymentStatus.FAILED
            self.db.add(payment)
            await self.db.commit()
            
            raise InvalidPaymentException("Payment verification failed")
    
    async def process_refund(
        self,
        order: Order,
        amount: Optional[Decimal] = None,
        reason: str = "Order cancelled"
    ) -> Dict[str, Any]:
        """
        Process refund for order
        
        Args:
            order: Order to refund
            amount: Refund amount (None for full refund)
            reason: Refund reason
            
        Returns:
            Refund details
        """
        # Get payment
        result = await self.db.execute(
            select(Payment)
            .where(and_(
                Payment.order_id == order.id,
                Payment.status == PaymentStatus.COMPLETED
            ))
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise NotFoundException("No completed payment found for order")
        
        # Calculate refund amount
        refund_amount = amount or payment.amount
        
        if refund_amount > payment.amount:
            raise BadRequestException("Refund amount cannot exceed payment amount")
        
        # Process refund based on payment method
        if payment.payment_method == PaymentMethod.COD:
            # No refund needed for COD
            return {
                "refund_id": f"cod_refund_{uuid.uuid4().hex[:8]}",
                "payment_id": payment.id,
                "amount": Decimal("0"),
                "status": "not_applicable",
                "created_at": datetime.utcnow()
            }
        
        # Process Razorpay refund
        try:
            refund = self.razorpay.create_refund(
                payment_id=payment.gateway_payment_id,
                amount=int(refund_amount * 100),  # Convert to paise
                notes={"reason": reason}
            )
            
            # Update payment status
            if refund_amount == payment.amount:
                payment.status = PaymentStatus.REFUNDED
            else:
                payment.status = PaymentStatus.PARTIALLY_REFUNDED
            
            payment.refund_amount = refund_amount
            payment.refund_reason = reason
            payment.refunded_at = datetime.utcnow()
            
            self.db.add(payment)
            await self.db.commit()
            
            # Send notification
            await self.notification_service.send_refund_processed(payment)
            
            return {
                "refund_id": refund["id"],
                "payment_id": payment.id,
                "amount": refund_amount,
                "status": refund["status"],
                "created_at": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Refund processing failed: {str(e)}")
            raise BadRequestException("Refund processing failed")
    
    async def get_payment_methods(self) -> List[Dict[str, Any]]:
        """
        Get available payment methods
        
        Returns:
            List of payment methods
        """
        methods = [
            {
                "method": PaymentMethod.CARD,
                "name": "Credit/Debit Card",
                "description": "Pay using credit or debit card",
                "icon": "/icons/card.svg",
                "is_available": True,
                "min_amount": Decimal("1"),
                "max_amount": Decimal("200000")
            },
            {
                "method": PaymentMethod.UPI,
                "name": "UPI",
                "description": "Pay using UPI ID or QR code",
                "icon": "/icons/upi.svg",
                "is_available": True,
                "min_amount": Decimal("1"),
                "max_amount": Decimal("100000")
            },
            {
                "method": PaymentMethod.NET_BANKING,
                "name": "Net Banking",
                "description": "Pay using internet banking",
                "icon": "/icons/netbanking.svg",
                "is_available": True,
                "min_amount": Decimal("1"),
                "max_amount": Decimal("500000")
            },
            {
                "method": PaymentMethod.WALLET,
                "name": "Wallet",
                "description": "Pay using digital wallets",
                "icon": "/icons/wallet.svg",
                "is_available": True,
                "min_amount": Decimal("1"),
                "max_amount": Decimal("50000")
            },
            {
                "method": PaymentMethod.COD,
                "name": "Cash on Delivery",
                "description": "Pay when you receive the order",
                "icon": "/icons/cod.svg",
                "is_available": True,
                "min_amount": Decimal("1"),
                "max_amount": Decimal("10000")
            }
        ]
        
        return methods
    
    async def handle_webhook(
        self,
        webhook_data: Dict[str, Any],
        signature: str
    ) -> None:
        """
        Handle payment webhook from gateway
        
        Args:
            webhook_data: Webhook payload
            signature: Webhook signature
        """
        # Verify webhook signature
        if not self.razorpay.verify_webhook_signature(
            payload=webhook_data,
            signature=signature
        ):
            raise InvalidPaymentException("Invalid webhook signature")
        
        # Handle different events
        event = webhook_data.get("event")
        
        if event == "payment.captured":
            await self._handle_payment_captured(webhook_data["payload"]["payment"]["entity"])
        elif event == "payment.failed":
            await self._handle_payment_failed(webhook_data["payload"]["payment"]["entity"])
        elif event == "refund.processed":
            await self._handle_refund_processed(webhook_data["payload"]["refund"]["entity"])
        else:
            logger.info(f"Unhandled webhook event: {event}")
    
    async def _handle_payment_captured(self, payment_data: Dict[str, Any]) -> None:
        """Handle payment captured webhook"""
        # Find payment by gateway payment ID
        result = await self.db.execute(
            select(Payment)
            .options(selectinload(Payment.order))
            .where(Payment.gateway_payment_id == payment_data["id"])
        )
        payment = result.scalar_one_or_none()
        
        if payment and payment.status != PaymentStatus.COMPLETED:
            payment.status = PaymentStatus.COMPLETED
            payment.order.payment_status = "completed"
            payment.order.status = OrderStatus.CONFIRMED
            
            self.db.add(payment)
            self.db.add(payment.order)
            await self.db.commit()
            
            await self.notification_service.send_payment_success(payment)
    
    async def _handle_payment_failed(self, payment_data: Dict[str, Any]) -> None:
        """Handle payment failed webhook"""
        # Find payment by gateway payment ID
        result = await self.db.execute(
            select(Payment)
            .where(Payment.gateway_payment_id == payment_data["id"])
        )
        payment = result.scalar_one_or_none()
        
        if payment:
            payment.status = PaymentStatus.FAILED
            payment.gateway_response = payment_data
            
            self.db.add(payment)
            await self.db.commit()
            
            await self.notification_service.send_payment_failed(payment)
    
    async def _handle_refund_processed(self, refund_data: Dict[str, Any]) -> None:
        """Handle refund processed webhook"""
        # Find payment by gateway payment ID
        result = await self.db.execute(
            select(Payment)
            .where(Payment.gateway_payment_id == refund_data["payment_id"])
        )
        payment = result.scalar_one_or_none()
        
        if payment:
            # Update refund status
            if refund_data["amount"] == payment.amount * 100:  # Full refund
                payment.status = PaymentStatus.REFUNDED
            else:
                payment.status = PaymentStatus.PARTIALLY_REFUNDED
            
            payment.refund_amount = Decimal(str(refund_data["amount"] / 100))
            payment.refunded_at = datetime.utcnow()
            
            self.db.add(payment)
            await self.db.commit()
