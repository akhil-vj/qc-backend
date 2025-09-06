"""Enhanced base schemas with validation"""

from pydantic import BaseModel, field_validator, Field, constr
from typing import Optional
from datetime import datetime
import uuid

from app.utils.validators import (
    validate_phone_number,
    validate_email_address,
    normalize_text,
    sanitize_html
)

class PhoneNumber(constr(strip_whitespace=True)):
    """Phone number type with validation"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
        
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("string required")
        return validate_phone_number(v)

class EmailAddress(constr(strip_whitespace=True, to_lower=True)):
    """Email type with validation"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
        
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("string required")
        return validate_email_address(v)

class BaseSchema(BaseModel):
    """Base schema with common configuration"""
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }

class UserCreateSchema(BaseSchema):
    """User creation schema with validation"""
    
    phone: PhoneNumber
    name: constr(min_length=2, max_length=100)
    email: Optional[EmailAddress] = None
    password: Optional[constr(min_length=8, max_length=100)] = None
    
    # Validators
    @validator("name")
    def normalize_name(cls, v):
        return normalize_text(v)
        
    @validator("password")
    def validate_password(cls, v):
        if v:
            from app.utils.validators import validate_password
            return validate_password(v)
        return v

class ProductCreateSchema(BaseSchema):
    """Product creation schema with validation"""
    
    title: constr(min_length=3, max_length=200)
    description: constr(min_length=10, max_length=5000)
    price: float = Field(..., gt=0, le=1000000)
    mrp: Optional[float] = Field(None, gt=0, le=1000000)
    stock: int = Field(..., ge=0, le=100000)
    
    @validator("title", "description")
    def normalize_text_fields(cls, v):
        return normalize_text(v)
        
    @validator("description")
    def sanitize_description(cls, v):
        return sanitize_html(v)
        
    @validator("mrp")
    def validate_mrp(cls, v, values):
        if v and "price" in values and v < values["price"]:
            raise ValueError("MRP cannot be less than selling price")
        return v
