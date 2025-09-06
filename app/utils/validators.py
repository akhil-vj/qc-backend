"""Custom validators and sanitizers"""

import re
from typing import Optional
from pydantic import validator, constr
import bleach
from email_validator import validate_email, EmailNotValidError

# Phone number regex patterns
PHONE_PATTERNS = {
    "IN": re.compile(r"^\+91[6-9]\d{9}$"),  # Indian phone numbers
    "US": re.compile(r"^\+1\d{10}$"),       # US phone numbers
    "DEFAULT": re.compile(r"^\+\d{7,15}$")  # International format
}

# OTP pattern
OTP_PATTERN = re.compile(r"^\d{6}$")

# Username pattern
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,30}$")

# File extensions
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}

def validate_phone_number(phone: str, country_code: str = "IN") -> str:
    """Validate and normalize phone number"""
    # Remove all non-digit characters except +
    phone = re.sub(r"[^\d+]", "", phone)
    
    # Add country code if missing
    if not phone.startswith("+"):
        if country_code == "IN" and len(phone) == 10:
            phone = f"+91{phone}"
        elif country_code == "US" and len(phone) == 10:
            phone = f"+1{phone}"
            
    # Validate format
    pattern = PHONE_PATTERNS.get(country_code, PHONE_PATTERNS["DEFAULT"])
    if not pattern.match(phone):
        raise ValueError(f"Invalid phone number format for {country_code}")
        
    return phone

def validate_otp(otp: str) -> str:
    """Validate OTP format"""
    otp = otp.strip()
    if not OTP_PATTERN.match(otp):
        raise ValueError("OTP must be 6 digits")
    return otp

def validate_email_address(email: str) -> str:
    """Validate and normalize email"""
    email = email.strip().lower()
    
    try:
        # Validate email
        validation = validate_email(email, check_deliverability=False)
        return validation.email
    except EmailNotValidError as e:
        raise ValueError(str(e))

def sanitize_html(html: str, allowed_tags: Optional[list] = None) -> str:
    """Sanitize HTML content"""
    if allowed_tags is None:
        allowed_tags = [
            'a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
            'em', 'i', 'li', 'ol', 'strong', 'ul', 'p', 'br',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
        ]
        
    allowed_attributes = {
        'a': ['href', 'title', 'target'],
        'abbr': ['title'],
        'acronym': ['title']
    }
    
    return bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True
    )

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for storage"""
    # Remove path separators and null bytes
    filename = filename.replace("/", "").replace("\\", "").replace("\x00", "")
    
    # Remove special characters
    filename = re.sub(r'[<>:"|?*]', '', filename)
    
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]
        
    return f"{name}{ext}".strip()

def validate_file_extension(filename: str, file_type: str = "image") -> bool:
    """Validate file extension"""
    ext = os.path.splitext(filename)[1].lower()
    
    if file_type == "image":
        return ext in ALLOWED_IMAGE_EXTENSIONS
    elif file_type == "document":
        return ext in ALLOWED_DOCUMENT_EXTENSIONS
        
    return False

def normalize_text(text: str) -> str:
    """Normalize text input"""
    # Remove extra whitespace
    text = " ".join(text.split())
    
    # Remove zero-width characters
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    
    # Trim
    return text.strip()

def validate_username(username: str) -> str:
    """Validate username format"""
    username = username.strip().lower()
    
    if not USERNAME_PATTERN.match(username):
        raise ValueError(
            "Username must be 3-30 characters long and contain only "
            "letters, numbers, underscores, and hyphens"
        )
        
    # Check for reserved usernames
    reserved = ["admin", "api", "root", "system", "test", "user"]
    if username in reserved:
        raise ValueError("This username is reserved")
        
    return username

def validate_password(password: str) -> str:
    """Validate password strength"""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
        
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
        
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
        
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
        
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValueError("Password must contain at least one special character")
        
    return password



# """
# Input validation utilities
# """

# import re
# from typing import Optional

# def phone_validator(phone: str) -> str:
#     """
#     Validate and normalize phone number
    
#     Args:
#         phone: Phone number
        
#     Returns:
#         Normalized phone number
        
#     Raises:
#         ValueError: If invalid
#     """
#     # Remove all non-digit characters except +
#     cleaned = re.sub(r'[^\d+]', '', phone)
    
#     # Check if it's an Indian number
#     if re.match(r'^(\+91)?[6-9]\d{9}$', cleaned):
#         # Normalize to +91 format
#         if not cleaned.startswith('+91'):
#             cleaned = '+91' + cleaned[-10:]
#         return cleaned
    
#     raise ValueError("Invalid Indian phone number")

# def email_validator(email: str) -> str:
#     """
#     Validate email address
    
#     Args:
#         email: Email address
        
#     Returns:
#         Normalized email
        
#     Raises:
#         ValueError: If invalid
#     """
#     email = email.lower().strip()
    
#     # Basic email regex
#     pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
#     if not re.match(pattern, email):
#         raise ValueError("Invalid email address")
    
#     return email

# def validate_indian_phone(phone: str) -> bool:
#     """Check if phone number is valid Indian number"""
#     pattern = r'^(\+91)?[6-9]\d{9}$'
#     cleaned = re.sub(r'[^\d+]', '', phone)
#     return bool(re.match(pattern, cleaned))

# def validate_pincode(pincode: str) -> bool:
#     """Validate Indian postal code"""
#     return bool(re.match(r'^\d{6}$', pincode))

# def validate_gst(gst: str) -> bool:
#     """Validate GST number format"""
#     pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
#     return bool(re.match(pattern, gst.upper()))

# def validate_pan(pan: str) -> bool:
#     """Validate PAN number format"""
#     pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
#     return bool(re.match(pattern, pan.upper()))

# def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
#     """
#     Sanitize user input string
    
#     Args:
#         text: Input text
#         max_length: Maximum allowed length
        
#     Returns:
#         Sanitized text
#     """
#     # Remove leading/trailing whitespace
#     text = text.strip()
    
#     # Remove multiple spaces
#     text = re.sub(r'\s+', ' ', text)
    
#     # Remove control characters
#     text = re.sub(r'[\x00-\x1F\x7F]', '', text)
    
#     # Limit length
#     if max_length:
#         text = text[:max_length]
    
#     return text
