"""
SMS service for sending OTP and notifications
"""

from typing import Optional
import asyncio
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

from app.core.config import settings

logger = logging.getLogger(__name__)

class SMSService:
    """SMS service using Twilio"""
    
    def __init__(self):
        self.enabled = bool(settings.TWILIO_ACCOUNT_SID)
        
        if self.enabled:
            self.client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            )
            self.from_number = settings.TWILIO_PHONE_NUMBER
        else:
            logger.warning("SMS service is disabled - Twilio credentials not configured")
    
    async def send_sms(
        self,
        to_phone: str,
        message: str
    ) -> bool:
        """
        Send SMS asynchronously
        
        Args:
            to_phone: Recipient phone number
            message: SMS content
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.info(f"SMS (disabled): To {to_phone} - {message}")
            return True
        
        try:
            # Run in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._send_sms_sync,
                to_phone,
                message
            )
        except Exception as e:
            logger.error(f"Failed to send SMS: {str(e)}")
            return False
    
    def _send_sms_sync(self, to_phone: str, message: str) -> bool:
        """Send SMS synchronously"""
        try:
            message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_phone
            )
            
            logger.info(f"SMS sent successfully: {message.sid}")
            return True
            
        except TwilioException as e:
            logger.error(f"Twilio error: {str(e)}")
            return False
    
    async def send_otp(self, phone: str, otp: str) -> bool:
        """Send OTP SMS"""
        message = f"Your QuickCart OTP is: {otp}. Valid for 5 minutes."
        return await self.send_sms(phone, message)
    
    async def send_order_update(
        self,
        phone: str,
        order_number: str,
        status: str
    ) -> bool:
        """Send order status update SMS"""
        message = f"Your order #{order_number} is now {status}. Track at quickcart.com/track"
        return await self.send_sms(phone, message)
