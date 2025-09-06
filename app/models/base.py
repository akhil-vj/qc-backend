"""Base models and mixins for database models"""

from sqlalchemy import Column, DateTime, Boolean, String, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, declared_attr, Session
from sqlalchemy.sql import func
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

# Create declarative base
class Base(DeclarativeBase):
    pass

class TimestampedModel:
    """Mixin for adding created_at and updated_at timestamps"""
    
    @declared_attr
    def created_at(cls):
        return Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            index=True
        )
    
    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now()
        )

class UUIDModel:
    """Mixin for adding UUID primary key"""
    
    @declared_attr
    def id(cls):
        return Column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            nullable=False
        )

class SoftDeleteModel:
    """Mixin for soft delete functionality"""
    
    @declared_attr
    def is_deleted(cls):
        return Column(
            Boolean,
            default=False,
            nullable=False,
            index=True
        )
    
    @declared_attr
    def deleted_at(cls):
        return Column(
            DateTime(timezone=True),
            nullable=True
        )
    
    def soft_delete(self):
        """Soft delete the record"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        
    def restore(self):
        """Restore soft deleted record"""
        self.is_deleted = False
        self.deleted_at = None

class BaseModel(Base):
    """Abstract base model with common functionality"""
    
    __abstract__ = True
    
    def to_dict(self, exclude: Optional[list] = None) -> Dict[str, Any]:
        """Convert model instance to dictionary"""
        exclude = exclude or []
        result = {}
        
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                
                # Handle special types
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif isinstance(value, uuid.UUID):
                    value = str(value)
                elif hasattr(value, 'to_dict'):
                    value = value.to_dict()
                    
                result[column.name] = value
                
        return result
    
    def update_from_dict(self, data: Dict[str, Any], exclude: Optional[list] = None):
        """Update model instance from dictionary"""
        exclude = exclude or []
        
        for key, value in data.items():
            if hasattr(self, key) and key not in exclude:
                setattr(self, key, value)
                
    def __repr__(self):
        """String representation"""
        class_name = self.__class__.__name__
        attributes = []
        
        for column in self.__table__.columns:
            if column.primary_key:
                value = getattr(self, column.name)
                attributes.append(f"{column.name}={value!r}")
                
        return f"<{class_name}({', '.join(attributes)})>"

class VersionedModel:
    """Mixin for version tracking"""
    
    @declared_attr
    def version(cls):
        return Column(
            Integer,
            nullable=False,
            default=1
        )
    
    def increment_version(self):
        """Increment version number"""
        self.version = (self.version or 0) + 1

class SluggedModel:
    """Mixin for URL-friendly slugs"""
    
    @declared_attr
    def slug(cls):
        return Column(
            String(255),
            nullable=True,
            unique=True,
            index=True
        )
    
    def generate_slug(self, text: str, db: Session) -> str:
        """Generate unique slug from text"""
        import re
        from sqlalchemy import func
        
        # Convert to lowercase and replace spaces with hyphens
        slug = text.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        
        # Ensure uniqueness
        base_slug = slug
        counter = 1
        
        while db.query(self.__class__).filter(
            self.__class__.slug == slug
        ).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
            
        return slug

class StatusModel:
    """Mixin for status tracking"""
    
    @declared_attr
    def status(cls):
        return Column(
            String(50),
            nullable=False,
            default='active',
            index=True
        )
    
    @declared_attr
    def status_changed_at(cls):
        return Column(
            DateTime(timezone=True),
            nullable=True
        )
    
    def change_status(self, new_status: str):
        """Change status and track time"""
        self.status = new_status
        self.status_changed_at = datetime.utcnow()

class AuditModel:
    """Mixin for audit fields"""
    
    @declared_attr
    def created_by(cls):
        return Column(
            UUID(as_uuid=True),
            nullable=True
        )
    
    @declared_attr
    def updated_by(cls):
        return Column(
            UUID(as_uuid=True),
            nullable=True
        )
    
    def set_audit_fields(self, user_id: str, is_create: bool = False):
        """Set audit fields"""
        if is_create:
            self.created_by = user_id
        self.updated_by = user_id

# Utility functions
def get_db_url(
    user: str,
    password: str,
    host: str,
    port: int,
    database: str
) -> str:
    """Generate database URL"""
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"

def create_tables(engine):
    """Create all tables"""
    Base.metadata.create_all(bind=engine)

def drop_tables(engine):
    """Drop all tables"""
    Base.metadata.drop_all(bind=engine)

# Model registry for easy access
model_registry = {}

def register_model(model_class):
    """Register a model in the registry"""
    model_registry[model_class.__name__] = model_class
    return model_class

# JSON encoder for models
import json
from decimal import Decimal

class ModelJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for models"""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)

# Export all
__all__ = [
    'Base',
    'BaseModel',
    'TimestampedModel',
    'UUIDModel',
    'SoftDeleteModel',
    'VersionedModel',
    'SluggedModel',
    'StatusModel',
    'AuditModel',
    'get_db_url',
    'create_tables',
    'drop_tables',
    'register_model',
    'model_registry',
    'ModelJSONEncoder'
]
