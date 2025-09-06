"""Complete email service with template rendering and sending"""

import smtplib
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import asyncio
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    """Complete email service with template rendering"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        self.from_name = settings.FROM_NAME
        
        # Setup Jinja2 for email templates
        template_dir = Path(__file__).parent.parent / "templates" / "emails"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Create template directory if it doesn't exist
        template_dir.mkdir(parents=True, exist_ok=True)
        
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """Send email with full features"""
        try:
            # Create message
            msg = MIMEMultipart('mixed')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            if reply_to:
                msg['Reply-To'] = reply_to
                
            # Create alternative part for text/html
            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)
            
            # Add text part
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg_alternative.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html', 'utf-8')
                msg_alternative.attach(html_part)
                
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    self._attach_file(msg, attachment)
                    
            # Prepare recipients
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
                
            # Send email
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                use_tls=True
            ) as smtp:
                await smtp.login(self.smtp_user, self.smtp_password)
                await smtp.send_message(msg, recipients=recipients)
                
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
            
    def _attach_file(self, msg: MIMEMultipart, attachment: Dict[str, Any]):
        """Attach file to email"""
        filename = attachment['filename']
        content = attachment['content']
        content_type = attachment.get('content_type', 'application/octet-stream')
        
        if content_type.startswith('image/'):
            part = MIMEImage(content, _subtype=content_type.split('/')[-1])
        elif content_type.startswith('text/'):
            part = MIMEText(content, _subtype=content_type.split('/')[-1])
        else:
            part = MIMEApplication(content)
            
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(part)
        
    async def send_otp_email(self, to_email: str, otp: str, name: str = "User"):
        """Send OTP verification email"""
        template = self.env.get_template("otp.html")
        html_body = template.render(
            name=name,
            otp=otp,
            validity_minutes=5,
            support_email=settings.SUPPORT_EMAIL,
            app_name="QuickCart"
        )
        
        return await self.send_email(
            to_email=to_email,
            subject="Your QuickCart Verification Code",
            body=f"Your verification code is: {otp}\n\nThis code is valid for 5 minutes.",
            html_body=html_body
        )
        
    async def send_order_confirmation(
        self,
        to_email: str,
        order_data: Dict[str, Any]
    ):
        """Send order confirmation email"""
        template = self.env.get_template("order_confirmation.html")
        
        # Prepare order data
        order_data['formatted_date'] = order_data['created_at'].strftime('%B %d, %Y')
        order_data['formatted_total'] = f"₹{order_data['total_amount']:,.2f}"
        order_data['app_url'] = settings.FRONTEND_URL
        order_data['track_url'] = f"{settings.FRONTEND_URL}/orders/{order_data['id']}"
        
        html_body = template.render(**order_data)
        
        return await self.send_email(
            to_email=to_email,
            subject=f"Order Confirmed - #{order_data['order_number']}",
            body=self._generate_text_version(order_data, 'order_confirmation'),
            html_body=html_body
        )
        
    async def send_welcome_email(self, to_email: str, name: str, user_type: str = "buyer"):
        """Send welcome email to new user"""
        template = self.env.get_template("welcome.html")
        
        # Customize content based on user type
        if user_type == "seller":
            next_steps = [
                "Complete your seller profile",
                "Add your first product",
                "Set up payment methods",
                "Review seller guidelines"
            ]
            cta_text = "Start Selling"
            cta_url = f"{settings.FRONTEND_URL}/seller/onboarding"
        else:
            next_steps = [
                "Browse our product categories",
                "Add items to your wishlist",
                "Set up delivery preferences",
                "Explore exclusive deals"
            ]
            cta_text = "Start Shopping"
            cta_url = f"{settings.FRONTEND_URL}/products"
            
        html_body = template.render(
            name=name,
            user_type=user_type,
            next_steps=next_steps,
            cta_text=cta_text,
            cta_url=cta_url,
            app_url=settings.FRONTEND_URL,
            referral_bonus="100 coins",
            support_email=settings.SUPPORT_EMAIL
        )
        
        return await self.send_email(
            to_email=to_email,
            subject="Welcome to QuickCart! 🎉",
            body=f"Welcome to QuickCart, {name}! We're excited to have you join our community.",
            html_body=html_body
        )
        
    async def send_password_reset(self, to_email: str, reset_token: str, name: str):
        """Send password reset email"""
        template = self.env.get_template("password_reset.html")
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        html_body = template.render(
            name=name,
            reset_url=reset_url,
            validity_hours=24,
            support_email=settings.SUPPORT_EMAIL,
            app_url=settings.FRONTEND_URL
        )
        
        return await self.send_email(
            to_email=to_email,
            subject="Reset Your Password - QuickCart",
            body=f"Click here to reset your password: {reset_url}",
            html_body=html_body
        )
        
    async def send_order_status_update(
        self,
        to_email: str,
        order_data: Dict[str, Any],
        new_status: str,
        tracking_info: Optional[Dict[str, Any]] = None
    ):
        """Send order status update email"""
        template = self.env.get_template("order_status_update.html")
        
        status_messages = {
            "confirmed": "Your order has been confirmed and is being prepared.",
            "shipped": "Your order has been shipped and is on its way!",
            "out_for_delivery": "Your order is out for delivery today.",
            "delivered": "Your order has been delivered successfully.",
            "cancelled": "Your order has been cancelled.",
            "refunded": "Your refund has been processed."
        }
        
        html_body = template.render(
            order_number=order_data['order_number'],
            status=new_status,
            status_message=status_messages.get(new_status, "Your order status has been updated."),
            tracking_info=tracking_info,
            order_url=f"{settings.FRONTEND_URL}/orders/{order_data['id']}",
            items=order_data.get('items', []),
            app_url=settings.FRONTEND_URL
        )
        
        return await self.send_email(
            to_email=to_email,
            subject=f"Order #{order_data['order_number']} - {new_status.replace('_', ' ').title()}",
            body=f"Your order #{order_data['order_number']} is now {new_status}.",
            html_body=html_body
        )
        
    async def send_abandoned_cart_reminder(
        self,
        to_email: str,
        user_name: str,
        cart_items: List[Dict[str, Any]],
        cart_total: float,
        discount_code: Optional[str] = None
    ):
        """Send abandoned cart reminder email"""
        template = self.env.get_template("abandoned_cart.html")
        
        html_body = template.render(
            user_name=user_name,
            cart_items=cart_items,
            cart_total=cart_total,
            discount_code=discount_code,
            discount_amount=10 if discount_code else 0,
            cart_url=f"{settings.FRONTEND_URL}/cart",
            app_url=settings.FRONTEND_URL
        )
        
        return await self.send_email(
            to_email=to_email,
            subject="You left something behind! 🛒",
            body=f"Hi {user_name}, you have items waiting in your cart.",
            html_body=html_body
        )
        
    async def send_promotional_email(
        self,
        to_email: str,
        campaign_data: Dict[str, Any]
    ):
        """Send promotional email"""
        template = self.env.get_template("promotional.html")
        
        html_body = template.render(
            **campaign_data,
            app_url=settings.FRONTEND_URL,
            unsubscribe_url=f"{settings.FRONTEND_URL}/unsubscribe?token={campaign_data.get('unsubscribe_token')}"
        )
        
        return await self.send_email(
            to_email=to_email,
            subject=campaign_data['subject'],
            body=campaign_data.get('text_content', ''),
            html_body=html_body
        )
        
    async def send_invoice(
        self,
        to_email: str,
        invoice_data: Dict[str, Any],
        pdf_attachment: bytes
    ):
        """Send invoice email with PDF attachment"""
        template = self.env.get_template("invoice.html")
        
        html_body = template.render(
            **invoice_data,
            app_url=settings.FRONTEND_URL
        )
        
        attachments = [{
            'filename': f"invoice_{invoice_data['invoice_number']}.pdf",
            'content': pdf_attachment,
            'content_type': 'application/pdf'
        }]
        
        return await self.send_email(
            to_email=to_email,
            subject=f"Invoice #{invoice_data['invoice_number']} - QuickCart",
            body=f"Please find attached invoice #{invoice_data['invoice_number']}",
            html_body=html_body,
            attachments=attachments
        )
        
    def _generate_text_version(self, data: Dict[str, Any], template_type: str) -> str:
        """Generate plain text version of email"""
        if template_type == 'order_confirmation':
            return f"""
Order Confirmation

Order Number: {data['order_number']}
Date: {data['formatted_date']}
Total: {data['formatted_total']}

Track your order: {data['track_url']}

Thank you for shopping with QuickCart!
"""
        return ""
        
    async def send_bulk_emails(
        self,
        recipients: List[Dict[str, str]],
        template_name: str,
        common_data: Dict[str, Any],
        batch_size: int = 50
    ) -> Dict[str, int]:
        """Send bulk emails with batching"""
        sent_count = 0
        failed_count = 0
        
        template = self.env.get_template(f"{template_name}.html")
        
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            tasks = []
            for recipient in batch:
                # Merge recipient data with common data
                email_data = {**common_data, **recipient}
                html_body = template.render(**email_data)
                
                task = self.send_email(
                    to_email=recipient['email'],
                    subject=common_data['subject'],
                    body=common_data.get('text_content', ''),
                    html_body=html_body
                )
                tasks.append(task)
                
            # Send batch concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    failed_count += 1
                    logger.error(f"Bulk email error: {str(result)}")
                elif result:
                    sent_count += 1
                else:
                    failed_count += 1
                    
            # Small delay between batches
            await asyncio.sleep(1)
            
        return {
            "sent": sent_count,
            "failed": failed_count,
            "total": len(recipients)
        }




# """Email service using SMTP"""

# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from email.mime.image import MIMEImage
# from typing import List, Optional, Dict, Any
# import logging
# from pathlib import Path
# import aiosmtplib
# from jinja2 import Environment, FileSystemLoader

# from app.core.config import settings

# logger = logging.getLogger(__name__)

# class EmailService:
#     """Service for sending emails"""
    
#     def __init__(self):
#         self.smtp_host = settings.SMTP_HOST
#         self.smtp_port = settings.SMTP_PORT
#         self.smtp_user = settings.SMTP_USER
#         self.smtp_password = settings.SMTP_PASSWORD
#         self.from_email = settings.FROM_EMAIL
#         self.from_name = settings.FROM_NAME
        
#         # Setup Jinja2 for email templates
#         template_dir = Path(__file__).parent.parent / "templates" / "emails"
#         self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        
#     async def send_email(
#         self,
#         to_email: str,
#         subject: str,
#         body: str,
#         html_body: Optional[str] = None,
#         attachments: Optional[List[Dict[str, Any]]] = None
#     ) -> bool:
#         """Send email"""
#         try:
#             # Create message
#             msg = MIMEMultipart('alternative')
#             msg['Subject'] = subject
#             msg['From'] = f"{self.from_name} <{self.from_email}>"
#             msg['To'] = to_email
            
#             # Add text part
#             text_part = MIMEText(body, 'plain')
#             msg.attach(text_part)
            
#             # Add HTML part if provided
#             if html_body:
#                 html_part = MIMEText(html_body, 'html')
#                 msg.attach(html_part)
                
#             # Add attachments if provided
#             if attachments:
#                 for attachment in attachments:
#                     # attachment = {"filename": "file.pdf", "content": bytes, "type": "application/pdf"}
#                     part = MIMEApplication(
#                         attachment["content"],
#                         Name=attachment["filename"]
#                     )
#                     part['Content-Disposition'] = f'attachment; filename="{attachment["filename"]}"'
#                     msg.attach(part)
                    
#             # Send email
#             async with aiosmtplib.SMTP(
#                 hostname=self.smtp_host,
#                 port=self.smtp_port,
#                 use_tls=True
#             ) as smtp:
#                 await smtp.login(self.smtp_user, self.smtp_password)
#                 await smtp.send_message(msg)
                
#             logger.info(f"Email sent successfully to {to_email}")
#             return True
            
#         except Exception as e:
#             logger.error(f"Failed to send email to {to_email}: {str(e)}")
#             return False
            
#     async def send_otp_email(self, to_email: str, otp: str, name: str = "User"):
#         """Send OTP verification email"""
#         template = self.env.get_template("otp.html")
#         html_body = template.render(
#             name=name,
#             otp=otp,
#             validity_minutes=5
#         )
        
#         return await self.send_email(
#             to_email=to_email,
#             subject="Your QuickCart OTP",
#             body=f"Your OTP is: {otp}. Valid for 5 minutes.",
#             html_body=html_body
#         )
        
#     async def send_order_confirmation(
#         self,
#         to_email: str,
#         order_data: Dict[str, Any]
#     ):
#         """Send order confirmation email"""
#         template = self.env.get_template("order_confirmation.html")
#         html_body = template.render(**order_data)
        
#         return await self.send_email(
#             to_email=to_email,
#             subject=f"Order Confirmed - #{order_data['order_number']}",
#             body=f"Your order #{order_data['order_number']} has been confirmed.",
#             html_body=html_body
#         )
        
#     async def send_welcome_email(self, to_email: str, name: str):
#         """Send welcome email to new user"""
#         template = self.env.get_template("welcome.html")
#         html_body = template.render(
#             name=name,
#             app_url=settings.FRONTEND_URL
#         )
        
#         return await self.send_email(
#             to_email=to_email,
#             subject="Welcome to QuickCart!",
#             body=f"Welcome to QuickCart, {name}!",
#             html_body=html_body
#         )
        
#     async def send_password_reset(self, to_email: str, reset_token: str, name: str):
#         """Send password reset email"""
#         template = self.env.get_template("password_reset.html")
#         reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
#         html_body = template.render(
#             name=name,
#             reset_url=reset_url,
#             validity_hours=24
#         )
        
#         return await self.send_email(
#             to_email=to_email,
#             subject="Reset Your Password",
#             body=f"Click here to reset your password: {reset_url}",
#             html_body=html_body
#         )
