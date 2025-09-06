"""
Razorpay payment gateway integration
"""

import razorpay
import hmac
import hashlib
from typing import Dict, Any, Optional
import json

from app.core.config import settings
from app.core.exceptions import InvalidPaymentException

class RazorpayClient:
    """Razorpay API client wrapper"""
    
    def __init__(self):
        self.client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        self.webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    
    def create_order(
        self,
        amount: int,
        currency: str = "INR",
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create Razorpay order
        
        Args:
            amount: Amount in smallest currency unit (paise for INR)
            currency: Currency code
            receipt: Receipt number
            notes: Additional notes
            
        Returns:
            Razorpay order details
        """
        try:
            order_data = {
                "amount": amount,
                "currency": currency,
                "receipt": receipt or "",
                "notes": notes or {}
            }
            
            order = self.client.order.create(data=order_data)
            return order
            
        except Exception as e:
            raise InvalidPaymentException(f"Failed to create payment order: {str(e)}")
    
    def fetch_order(self, order_id: str) -> Dict[str, Any]:
        """
        Fetch Razorpay order details
        
        Args:
            order_id: Razorpay order ID
            
        Returns:
            Order details
        """
        try:
            return self.client.order.fetch(order_id)
        except Exception as e:
            raise InvalidPaymentException(f"Failed to fetch order: {str(e)}")
    
    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Fetch payment details
        
        Args:
            payment_id: Razorpay payment ID
            
        Returns:
            Payment details
        """
        try:
            return self.client.payment.fetch(payment_id)
        except Exception as e:
            raise InvalidPaymentException(f"Failed to fetch payment: {str(e)}")
    
    def capture_payment(
        self,
        payment_id: str,
        amount: int,
        currency: str = "INR"
    ) -> Dict[str, Any]:
        """
        Capture payment
        
        Args:
            payment_id: Razorpay payment ID
            amount: Amount to capture
            currency: Currency code
            
        Returns:
            Captured payment details
        """
        try:
            return self.client.payment.capture(
                payment_id,
                amount,
                {"currency": currency}
            )
        except Exception as e:
            raise InvalidPaymentException(f"Failed to capture payment: {str(e)}")
    
    def create_refund(
        self,
        payment_id: str,
        amount: Optional[int] = None,
        notes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create refund for payment
        
        Args:
            payment_id: Razorpay payment ID
            amount: Refund amount (None for full refund)
            notes: Additional notes
            
        Returns:
            Refund details
        """
        try:
            refund_data = {"payment_id": payment_id}
            
            if amount is not None:
                refund_data["amount"] = amount
                
            if notes:
                refund_data["notes"] = notes
            
            return self.client.refund.create(data=refund_data)
            
        except Exception as e:
            raise InvalidPaymentException(f"Failed to create refund: {str(e)}")
    
    def verify_payment_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str
    ) -> bool:
        """
        Verify payment signature
        
        Args:
            order_id: Razorpay order ID
            payment_id: Razorpay payment ID
            signature: Payment signature
            
        Returns:
            True if signature is valid
        """
        try:
            # Create signature string
            signature_string = f"{order_id}|{payment_id}"
            
            # Generate expected signature
            expected_signature = hmac.new(
                self.client.auth[1].encode('utf-8'),
                signature_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception:
            return False
    
    def verify_webhook_signature(
        self,
        payload: Dict[str, Any],
        signature: str
    ) -> bool:
        """
        Verify webhook signature
        
        Args:
            payload: Webhook payload
            signature: Webhook signature from headers

        Returns:
            True if signature is valid
        """
        try:
            # Convert payload to JSON string
            payload_string = json.dumps(payload, separators=(',', ':'))
            
            # Generate expected signature
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception:
            return False
