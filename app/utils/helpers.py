"""
Helper utilities
"""

import re
import math
from typing import Optional, Tuple
from decimal import Decimal
import slugify as python_slugify
from datetime import datetime, timedelta

def generate_slug(text: str) -> str:
    """
    Generate URL-friendly slug from text
    
    Args:
        text: Input text
        
    Returns:
        Slug
    """
    return python_slugify.slugify(text)

def format_currency(
    amount: Decimal,
    currency: str = "INR",
    locale: str = "en_IN"
) -> str:
    """
    Format amount as currency
    
    Args:
        amount: Amount to format
        currency: Currency code
        locale: Locale for formatting
        
    Returns:
        Formatted currency string
    """
    if currency == "INR":
        # Format for Indian Rupees
        amount_str = str(amount)
        
        # Split into integer and decimal parts
        parts = amount_str.split('.')
        integer_part = parts[0]
        decimal_part = parts[1] if len(parts) > 1 else "00"
        
        # Add commas for Indian numbering
        if len(integer_part) > 3:
            # Last 3 digits
            result = integer_part[-3:]
            integer_part = integer_part[:-3]
            
            # Add commas every 2 digits
            while integer_part:
                result = integer_part[-2:] + "," + result
                integer_part = integer_part[:-2]
            
            return f"₹{result}.{decimal_part[:2]}"
        else:
            return f"₹{integer_part}.{decimal_part[:2]}"
    
    # Default formatting for other currencies
    return f"{currency} {amount:.2f}"

def calculate_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:
    """
    Calculate distance between two coordinates using Haversine formula
    
    Args:
        lat1, lon1: First coordinate
        lat2, lon2: Second coordinate
        
    Returns:
        Distance in kilometers
    """
    # Earth's radius in kilometers
    R = 6371
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = (
        math.sin(delta_lat / 2) ** 2 +
        math.cos(lat1_rad) * math.cos(lat2_rad) *
        math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def calculate_delivery_date(
    order_date: datetime,
    shipping_method: str = "standard"
) -> datetime:
    """
    Calculate expected delivery date
    
    Args:
        order_date: Order placement date
        shipping_method: Shipping method
        
    Returns:
        Expected delivery date
    """
    delivery_days = {
        "express": 1,
        "standard": 3,
        "economy": 7
    }
    
    days = delivery_days.get(shipping_method, 3)
    
    # Skip weekends
    delivery_date = order_date
    while days > 0:
        delivery_date += timedelta(days=1)
        if delivery_date.weekday() < 5:  # Monday to Friday
            days -= 1
    
    return delivery_date

def mask_phone(phone: str) -> str:
    """
    Mask phone number for privacy
    
    Args:
        phone: Phone number
        
    Returns:
        Masked phone number
    """
    if len(phone) >= 10:
        return f"{phone[:3]}****{phone[-3:]}"
    return "****"

def mask_email(email: str) -> str:
    """
    Mask email for privacy
    
    Args:
        email: Email address
        
    Returns:
        Masked email
    """
    parts = email.split('@')
    if len(parts) == 2:
        username = parts[0]
        domain = parts[1]
        
        if len(username) > 2:
            masked_username = username[0] + "*" * (len(username) - 2) + username[-1]
        else:
            masked_username = "*" * len(username)
        
        return f"{masked_username}@{domain}"
    
    return "****"

def generate_order_number(prefix: str = "ORD") -> str:
    """Generate unique order number"""
    from datetime import datetime
    import random
    import string
    
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    return f"{prefix}{timestamp}{random_suffix}"
