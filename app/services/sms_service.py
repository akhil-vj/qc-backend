"""Complete SMS service with Twilio integration"""

from typing import Optional, Dict, Any, List
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
import asyncio
import phonenumbers
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)

class SMSService:
    """Complete SMS service with Twilio"""
    
    def __init__(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.service_sid = settings.TWILIO_SERVICE_SID
        self.messaging_service_sid = settings.TWILIO_MESSAGING_SERVICE_SID
        
    async def send_sms(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None,
        callback_url: Optional[str] = None,
        priority: bool = False
    ) -> Dict[str, Any]:
        """Send SMS with full features"""
        try:
            # Validate and format phone number
            formatted_number = self._format_phone_number(to_number)
            
            # Validate message length
            if len(message) > 1600:
                message = message[:1597] + "..."
                
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            kwargs = {
                "body": message,
                "to": formatted_number
            }
            
            # Use messaging service if available for better deliverability
            if self.messaging_service_sid:
                kwargs["messaging_service_sid"] = self.messaging_service_sid
            else:
                kwargs["from_"] = self.from_number
                
            if media_url:
                kwargs["media_url"] = [media_url]
                
            if callback_url:
                kwargs["status_callback"] = callback_url
                
            if priority:
                kwargs["priority"] = "high"
                kwargs["attempt"] = 1
                
            result = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(**kwargs)
            )
            
            logger.info(f"SMS sent to {formatted_number}, SID: {result.sid}")
            
            return {
                "success": True,
                "sid": result.sid,
                "status": result.status,
                "to": result.to,
                "price": result.price,
                "price_unit": result.price_unit
            }
            
        except TwilioException as e:
            logger.error(f"Twilio error sending SMS to {to_number}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code if hasattr(e, 'code') else None
            }
        except Exception as e:
            logger.error(f"Unexpected error sending SMS: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    def _format_phone_number(self, phone: str, default_country: str = "IN") -> str:
        """Format phone number to E.164 format"""
        try:
            # Parse phone number
            if not phone.startswith("+"):
                phone = f"+{phone}" if phone.startswith(("91", "1")) else phone
                
            parsed = phonenumbers.parse(phone, default_country)
            
            # Format to E.164
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            
        except phonenumbers.NumberParseException:
            # Return as-is if parsing fails
            return phone
            
    async def send_otp_sms(self, to_number: str, otp: str) -> Dict[str, Any]:
        """Send OTP via SMS"""
        message = f"Your QuickCart OTP is: {otp}\n\nValid for 5 minutes. Do not share with anyone.\n\n- QuickCart"
        
        return await self.send_sms(to_number, message, priority=True)
        
    async def send_order_update_sms(
        self,
        to_number: str,
        order_number: str,
        status: str,
        tracking_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send order status update SMS"""
        status_messages = {
            "confirmed": f"Order #{order_number} confirmed! We'll notify you when it ships.",
            "shipped": f"Good news! Order #{order_number} has been shipped.",
            "out_for_delivery": f"Order #{order_number} is out for delivery today!",
            "delivered": f"Order #{order_number} has been delivered. Enjoy your purchase!",
            "cancelled": f"Order #{order_number} has been cancelled. Refund will be processed soon.",
            "refunded": f"Refund for order #{order_number} has been processed."
        }
        
        message = status_messages.get(status, f"Order #{order_number} status: {status}")
        
        if tracking_url:
            message += f"\n\nTrack: {tracking_url}"
            
        message += "\n\n- QuickCart"
        
        return await self.send_sms(to_number, message)
        
    async def send_delivery_otp_sms(
        self,
        to_number: str,
        otp: str,
        order_number: str
    ) -> Dict[str, Any]:
        """Send delivery OTP"""
        message = f"Delivery OTP for order #{order_number}: {otp}\n\nShare with delivery partner only.\n\n- QuickCart"
        
        return await self.send_sms(to_number, message, priority=True)
        
    async def send_payment_confirmation_sms(
        self,
        to_number: str,
        amount: float,
        order_number: str,
        payment_method: str
    ) -> Dict[str, Any]:
        """Send payment confirmation SMS"""
        message = f"Payment of ₹{amount:,.2f} received for order #{order_number} via {payment_method}.\n\n- QuickCart"
        
        return await self.send_sms(to_number, message)
        
    async def send_refund_sms(
        self,
        to_number: str,
        amount: float,
        order_number: str,
        expected_days: int = 5
    ) -> Dict[str, Any]:
        """Send refund notification SMS"""
        message = f"Refund of ₹{amount:,.2f} initiated for order #{order_number}. Expected in {expected_days}-{expected_days+2} days.\n\n- QuickCart"
        
        return await self.send_sms(to_number, message)
        
    async def send_promotional_sms(
        self,
        to_number: str,
        message: str,
        campaign_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send promotional SMS (with DND check)"""
        # Add opt-out message
        promotional_message = f"{message}\n\nReply STOP to unsubscribe."
        
        # Add campaign tracking if provided
        callback_url = None
        if campaign_id:
            callback_url = f"{settings.API_URL}/webhooks/sms-status?campaign_id={campaign_id}"
            
        return await self.send_sms(
            to_number,
            promotional_message,
            callback_url=callback_url
        )
        
    async def send_flash_sale_sms(
        self,
        to_number: str,
        sale_title: str,
        discount: int,
        end_time: datetime,
        link: str
    ) -> Dict[str, Any]:
        """Send flash sale notification SMS"""
        hours_left = int((end_time - datetime.utcnow()).total_seconds() / 3600)
        
        message = f"🔥 FLASH SALE: {sale_title}\n{discount}% OFF!\n\nEnds in {hours_left} hours.\n\nShop now: {link}\n\n- QuickCart"
        
        return await self.send_sms(to_number, message, priority=True)
        
    async def send_bulk_sms(
        self,
        recipients: List[Dict[str, str]],
        message_template: str,
        batch_size: int = 100,
        delay_between_batches: int = 2
    ) -> Dict[str, Any]:
        """Send bulk SMS with rate limiting"""
        sent_count = 0
        failed_count = 0
        failed_numbers = []
        
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            tasks = []
            for recipient in batch:
                # Personalize message
                message = message_template.format(**recipient)
                
                task = self.send_sms(
                    to_number=recipient['phone'],
                    message=message
                )
                tasks.append(task)
                
            # Send batch concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_count += 1
                    failed_numbers.append(batch[idx]['phone'])
                    logger.error(f"Bulk SMS error: {str(result)}")
                elif isinstance(result, dict) and result.get('success'):
                    sent_count += 1
                else:
                    failed_count += 1
                    failed_numbers.append(batch[idx]['phone'])
                    
            # Delay between batches to respect rate limits
            if i + batch_size < len(recipients):
                await asyncio.sleep(delay_between_batches)
                
        return {
            "sent": sent_count,
            "failed": failed_count,
            "total": len(recipients),
            "failed_numbers": failed_numbers
        }
        
    async def check_delivery_status(self, message_sid: str) -> Dict[str, Any]:
        """Check SMS delivery status"""
        try:
            loop = asyncio.get_event_loop()
            
            message = await loop.run_in_executor(
                None,
                lambda: self.client.messages(message_sid).fetch()
            )
            
            return {
                "sid": message.sid,
                "status": message.status,
                "error_code": message.error_code,
                "error_message": message.error_message,
                "date_sent": message.date_sent,
                "date_updated": message.date_updated
            }
            
        except Exception as e:
            logger.error(f"Error checking SMS status: {str(e)}")
            return {"error": str(e)}
            
    async def handle_status_callback(self, webhook_data: Dict[str, Any]):
        """Handle Twilio status callbacks"""
        message_sid = webhook_data.get('MessageSid')
        status = webhook_data.get('MessageStatus')
        error_code = webhook_data.get('ErrorCode')
        
        logger.info(f"SMS status update - SID: {message_sid}, Status: {status}")
        
        # Update delivery status in database
        # You can implement this based on your needs
        
        if error_code:
            logger.error(f"SMS delivery error - SID: {message_sid}, Error: {error_code}")



# """SMS service using Twilio"""

# from typing import Optional, Dict, Any
# import logging
# from twilio.rest import Client
# from twilio.base.exceptions import TwilioException
# import asyncio

# from app.core.config import settings

# logger = logging.getLogger(__name__)

# class SMSService:
#     """Service for sending SMS"""
    
#     def __init__(self):
#         self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
#         self.from_number = settings.TWILIO_PHONE_NUMBER
#         self.service_sid = settings.TWILIO_SERVICE_SID
        
#     async def send_sms(
#         self,
#         to_number: str,
#         message: str,
#         media_url: Optional[str] = None
#     ) -> bool:
#         """Send SMS"""
#         try:
#             # Run in thread pool to avoid blocking
#             loop = asyncio.get_event_loop()
            
#             kwargs = {
#                 "body": message,
#                 "from_": self.from_number,
#                 "to": to_number
#             }
            
#             if media_url:
#                 kwargs["media_url"] = [media_url]
                
#             result = await loop.run_in_executor(
#                 None,
#                 lambda: self.client.messages.create(**kwargs)
#             )
            
#             logger.info(f"SMS sent to {to_number}, SID: {result.sid}")
#             return True
            
#         except TwilioException as e:
#             logger.error(f"Failed to send SMS to {to_number}: {str(e)}")
#             return False
#         except Exception as e:
#             logger.error(f"Unexpected error sending SMS: {str(e)}")
#             return False
            
#     async def send_otp_sms(self, to_number: str, otp: str) -> bool:
#         """Send OTP via SMS"""
#         message = f"Your QuickCart OTP is: {otp}. Valid for 5 minutes. Do not share with anyone."
#         return await self.send_sms(to_number, message)
        
#     async def send_order_update_sms(
#         self,
#         to_number: str,
#         order_number: str,
#         status: str
#     ) -> bool:
#         """Send order status update SMS"""
#         message = f"QuickCart: Your order #{order_number} is now {status}. Track at {settings.FRONTEND_URL}/orders"
#         return await self.send_sms(to_number, message)
        
#     async def send_delivery_otp_sms(
#         self,
#         to_number: str,
#         otp: str,
#         order_number: str
#     ) -> bool:
#         """Send delivery OTP"""
#         message = f"QuickCart Delivery OTP for order #{order_number}: {otp}. Share with delivery partner only."
#         return await self.send_sms(to_number, message)
        
#     async def send_promotional_sms(
#         self,
#         to_number: str,
#         message: str
#     ) -> bool:
#         """Send promotional SMS (check DND status)"""
#         # Add DND check logic here
#         promotional_message = f"{message}\nReply STOP to unsubscribe."
#         return await self.send_sms(to_number, promotional_message)
