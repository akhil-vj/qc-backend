"""
Address model for shipping and billing
"""

from sqlalchemy import Column, String, Boolean, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from .base import Base, TimestampedModel

class Address(Base, TimestampedModel):
    """User addresses for shipping/billing"""
    
    __tablename__ = "addresses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Address details
    label = Column(String(100), nullable=False)  # Home, Office, etc.
    recipient_name = Column(String(255), nullable=False)
    phone = Column(String(15), nullable=False)
    
    # Location
    address_line1 = Column(String(500), nullable=False)
    address_line2 = Column(String(500), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    postal_code = Column(String(20), nullable=False)
    country = Column(String(100), default="India", nullable=False)
    
    # Coordinates (for delivery optimization)
    latitude = Column(Numeric(10, 8), nullable=True)
    longitude = Column(Numeric(11, 8), nullable=True)
    
    # Flags
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="addresses")
    
    # Indexes
    __table_args__ = (
        Index("idx_addresses_user_active", "user_id", "is_active"),
        Index("idx_addresses_postal_code", "postal_code"),
    )
