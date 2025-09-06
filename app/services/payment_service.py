"""Payment service for handling payments, refunds and transactions."""

from typing import Optional, Dict, Any, List
from decimal import Decimal
import razorpay
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.models.order import Order, OrderStatus
from app.schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse
from app.services.notification_service import NotificationService
from app.core.audit_decorator import audit_action
import logging

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)
        
        # Initialize Razorpay client
        self.razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

    @audit_action("create_payment_order")
    async def create_payment_order(
        self, 
        order_id: str, 
        amount: Decimal,
        currency: str = "INR"
    ) -> Dict[str, Any]:
        """Create Razorpay payment order."""
        try:
            # Get order details
            order = self.db.query(Order).filter(Order.id == order_id).first()
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found"
                )

            # Create Razorpay order
            razorpay_order = self.razorpay_client.order.create({
                'amount': int(amount * 100),  # Convert to paise
                'currency': currency,
                'receipt': f'order_{order_id}',
                'payment_capture': 1  # Auto capture
            })

            # Create payment record
            payment = Payment(
                order_id=order_id,
                amount=amount,
                currency=currency,
                method=PaymentMethod.RAZORPAY,
                status=PaymentStatus.PENDING,
                gateway_order_id=razorpay_order['id'],
                metadata={'razorpay_order': razorpay_order}
            )
            
            self.db.add(payment)
            self.db.commit()
            self.db.refresh(payment)

            return {
                'payment_id': payment.id,
                'razorpay_order_id': razorpay_order['id'],
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'amount': amount,
                'currency': currency,
                'order_id': order_id
            }

        except Exception as e:
            logger.error(f"Failed to create payment order: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create payment order"
            )

    @audit_action("verify_payment")
    async def verify_payment(
        self,
        payment_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> PaymentResponse:
        """Verify Razorpay payment signature."""
        try:
            # Get payment record
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )

            # Verify signature
            params_dict = {
                'razorpay_order_id': payment.gateway_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }

            self.razorpay_client.utility.verify_payment_signature(params_dict)

            # Update payment status
            payment.gateway_payment_id = razorpay_payment_id
            payment.status = PaymentStatus.COMPLETED
            payment.metadata.update({
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })

            # Update order status
            order = self.db.query(Order).filter(Order.id == payment.order_id).first()
            if order:
                order.status = OrderStatus.CONFIRMED
                order.payment_status = 'paid'

            self.db.commit()
            self.db.refresh(payment)

            # Send confirmation notifications
            await self._send_payment_confirmation(payment)

            return PaymentResponse.from_orm(payment)

        except razorpay.errors.SignatureVerificationError:
            # Update payment as failed
            payment.status = PaymentStatus.FAILED
            payment.metadata.update({'error': 'Invalid signature'})
            self.db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment signature"
            )
        except Exception as e:
            logger.error(f"Payment verification failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment verification failed"
            )

    @audit_action("process_refund")
    async def process_refund(
        self,
        payment_id: str,
        amount: Optional[Decimal] = None,
        reason: str = "Customer request"
    ) -> Dict[str, Any]:
        """Process payment refund."""
        try:
            # Get payment record
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found"
                )

            if payment.status != PaymentStatus.COMPLETED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Can only refund completed payments"
                )

            # Calculate refund amount
            refund_amount = amount or payment.amount
            if refund_amount > payment.amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Refund amount cannot exceed payment amount"
                )

            # Create Razorpay refund
            refund = self.razorpay_client.payment.refund(
                payment.gateway_payment_id,
                {
                    'amount': int(refund_amount * 100),  # Convert to paise
                    'reason': reason
                }
            )

            # Update payment status
            payment.status = PaymentStatus.REFUNDED
            payment.refund_amount = refund_amount
            payment.metadata.update({
                'refund': refund,
                'refund_reason': reason
            })

            # Update order status
            order = self.db.query(Order).filter(Order.id == payment.order_id).first()
            if order:
                order.status = OrderStatus.REFUNDED
                order.payment_status = 'refunded'

            self.db.commit()

            # Send refund notification
            await self._send_refund_notification(payment, refund_amount)

            return {
                'refund_id': refund['id'],
                'amount': refund_amount,
                'status': 'processed'
            }

        except Exception as e:
            logger.error(f"Refund processing failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Refund processing failed"
            )

    def get_payment(self, payment_id: str) -> Optional[Payment]:
        """Get payment by ID."""
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def get_order_payments(self, order_id: str) -> List[Payment]:
        """Get all payments for an order."""
        return self.db.query(Payment).filter(Payment.order_id == order_id).all()

    def get_user_payments(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Payment]:
        """Get all payments for a user."""
        return (
            self.db.query(Payment)
            .join(Order)
            .filter(Order.customer_id == user_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @audit_action("handle_webhook")
    async def handle_webhook(self, event: Dict[str, Any]) -> bool:
        """Handle Razorpay webhooks."""
        try:
            event_type = event.get('event')
            payload = event.get('payload', {})
            
            if event_type == 'payment.captured':
                payment_entity = payload.get('payment', {}).get('entity', {})
                razorpay_payment_id = payment_entity.get('id')
                razorpay_order_id = payment_entity.get('order_id')
                
                # Find payment by order ID
                payment = (
                    self.db.query(Payment)
                    .filter(Payment.gateway_order_id == razorpay_order_id)
                    .first()
                )
                
                if payment and payment.status == PaymentStatus.PENDING:
                    payment.gateway_payment_id = razorpay_payment_id
                    payment.status = PaymentStatus.COMPLETED
                    payment.metadata.update({'webhook_event': event})
                    
                    # Update order
                    order = self.db.query(Order).filter(Order.id == payment.order_id).first()
                    if order:
                        order.status = OrderStatus.CONFIRMED
                        order.payment_status = 'paid'
                    
                    self.db.commit()
                    
                    # Send confirmation
                    await self._send_payment_confirmation(payment)
                    
            elif event_type == 'payment.failed':
                payment_entity = payload.get('payment', {}).get('entity', {})
                razorpay_order_id = payment_entity.get('order_id')
                
                # Find and update payment
                payment = (
                    self.db.query(Payment)
                    .filter(Payment.gateway_order_id == razorpay_order_id)
                    .first()
                )
                
                if payment:
                    payment.status = PaymentStatus.FAILED
                    payment.metadata.update({'webhook_event': event})
                    self.db.commit()
                    
                    # Send failure notification
                    await self._send_payment_failure_notification(payment)

            return True

        except Exception as e:
            logger.error(f"Webhook handling failed: {str(e)}")
            return False

    async def _send_payment_confirmation(self, payment: Payment):
        """Send payment confirmation notifications."""
        try:
            order = self.db.query(Order).filter(Order.id == payment.order_id).first()
            if order:
                await self.notification_service.send_notification(
                    user_id=order.customer_id,
                    title="Payment Successful!",
                    body=f"Your payment of ₹{payment.amount} has been confirmed. Order #{order.order_number}",
                    type="payment_success",
                    metadata={
                        'order_id': order.id,
                        'payment_id': payment.id,
                        'amount': str(payment.amount)
                    }
                )
        except Exception as e:
            logger.error(f"Failed to send payment confirmation: {str(e)}")

    async def _send_refund_notification(self, payment: Payment, refund_amount: Decimal):
        """Send refund notification."""
        try:
            order = self.db.query(Order).filter(Order.id == payment.order_id).first()
            if order:
                await self.notification_service.send_notification(
                    user_id=order.customer_id,
                    title="Refund Processed",
                    body=f"Your refund of ₹{refund_amount} has been processed. Order #{order.order_number}",
                    type="refund_success",
                    metadata={
                        'order_id': order.id,
                        'payment_id': payment.id,
                        'refund_amount': str(refund_amount)
                    }
                )
        except Exception as e:
            logger.error(f"Failed to send refund notification: {str(e)}")

    async def _send_payment_failure_notification(self, payment: Payment):
        """Send payment failure notification."""
        try:
            order = self.db.query(Order).filter(Order.id == payment.order_id).first()
            if order:
                await self.notification_service.send_notification(
                    user_id=order.customer_id,
                    title="Payment Failed",
                    body=f"Your payment for Order #{order.order_number} could not be processed. Please try again.",
                    type="payment_failed",
                    metadata={
                        'order_id': order.id,
                        'payment_id': payment.id
                    }
                )
        except Exception as e:
            logger.error(f"Failed to send payment failure notification: {str(e)}")

    def get_payment_analytics(self, user_id: str) -> Dict[str, Any]:
        """Get payment analytics for admin."""
        from sqlalchemy import func
        
        # Total payments
        total_payments = self.db.query(func.count(Payment.id)).scalar()
        
        # Successful payments
        successful_payments = (
            self.db.query(func.count(Payment.id))
            .filter(Payment.status == PaymentStatus.COMPLETED)
            .scalar()
        )
        
        # Total amount
        total_amount = (
            self.db.query(func.sum(Payment.amount))
            .filter(Payment.status == PaymentStatus.COMPLETED)
            .scalar() or 0
        )
        
        # Success rate
        success_rate = (successful_payments / total_payments * 100) if total_payments > 0 else 0
        
        return {
            'total_payments': total_payments,
            'successful_payments': successful_payments,
            'failed_payments': total_payments - successful_payments,
            'total_amount': float(total_amount),
            'success_rate': round(success_rate, 2)
        }
