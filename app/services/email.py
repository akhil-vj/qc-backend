"""
Email service for sending transactional emails
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import asyncio
from jinja2 import Template
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailService:
    """Email service using SMTP"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.from_name = settings.SMTP_FROM_NAME
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send email asynchronously
        
        Args:
            to_email: Recipient email
            subject: Email subject
            html_content: HTML content
            text_content: Plain text content
            
        Returns:
            True if sent successfully
        """
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._send_email_sync,
                to_email,
                subject,
                html_content,
                text_content
            )
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    def _send_email_sync(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send email synchronously
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Add plain text part
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            # Add HTML part
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"SMTP error: {str(e)}")
            return False
    
    async def send_welcome_email(self, user_email: str, user_name: str) -> bool:
        """Send welcome email to new user"""
        template = """
        <html>
            <body>
                <h2>Welcome to QuickCart, {{ name }}!</h2>
                <p>Thank you for joining our community-driven shopping platform.</p>
                <p>Start exploring amazing products and deals today!</p>
                <a href="https://quickcart.com" style="background-color: #3B82F6; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                    Start Shopping
                </a>
            </body>
        </html>
        """
        
        html_content = Template(template).render(name=user_name)
        
        return await self.send_email(
            to_email=user_email,
            subject="Welcome to QuickCart!",
            html_content=html_content
        )
    
    async def send_order_confirmation(
        self,
        user_email: str,
        order_number: str,
        total_amount: str
    ) -> bool:
        """Send order confirmation email"""
        template = """
        <html>
            <body>
                <h2>Order Confirmed!</h2>
                <p>Your order #{{ order_number }} has been confirmed.</p>
                <p>Total Amount: ₹{{ total_amount }}</p>
                <p>You can track your order status in your account.</p>
            </body>
        </html>
        """
        
        html_content = Template(template).render(
            order_number=order_number,
            total_amount=total_amount
        )
        
        return await self.send_email(
            to_email=user_email,
            subject=f"Order #{order_number} Confirmed",
            html_content=html_content
        )
