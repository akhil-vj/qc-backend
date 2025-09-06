"""CMS models for static pages"""

from sqlalchemy import Column, String, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.models.base import Base, TimestampedModel

class CMSPage(Base, TimestampedModel):
    """CMS page model"""
    
    __tablename__ = "cms_pages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    meta_description = Column(String(500))
    meta_keywords = Column(String(500))
    is_published = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)  # Protected pages
    order = Column(Integer, default=0)
    
    # Version tracking
    version = Column(Integer, default=1)
    published_version = Column(Integer, default=1)

class CMSPageVersion(Base, TimestampedModel):
    """CMS page version history"""
    
    __tablename__ = "cms_page_versions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id = Column(UUID(as_uuid=True), ForeignKey("cms_pages.id"), nullable=False)
    version = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    meta_description = Column(String(500))
    meta_keywords = Column(String(500))
    modified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Relationships
    page = relationship("CMSPage", backref="versions")
    modifier = relationship("User")
    
    __table_args__ = (
        UniqueConstraint("page_id", "version"),
    )

class FAQ(Base, TimestampedModel):
    """FAQ model"""
    
    __tablename__ = "faqs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(100), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    order = Column(Integer, default=0)
    is_published = Column(Boolean, default=True)



# """CMS models for static pages"""

# from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Integer
# from sqlalchemy.dialects.postgresql import UUID
# from sqlalchemy.orm import relationship
# import uuid

# from app.models.base import Base, TimestampedModel

# class StaticPage(Base, TimestampedModel):
#     """Static pages manageable by admin"""
    
#     __tablename__ = "static_pages"
    
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     slug = Column(String(100), unique=True, nullable=False, index=True)
#     title = Column(String(200), nullable=False)
#     content = Column(Text, nullable=False)
#     meta_title = Column(String(200))
#     meta_description = Column(Text)
#     meta_keywords = Column(String(500))
#     is_published = Column(Boolean, default=True)
#     order = Column(Integer, default=0)
    
#     # Audit fields
#     created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
#     updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
#     # Relationships
#     creator = relationship("User", foreign_keys=[created_by])
#     updater = relationship("User", foreign_keys=[updated_by])
#     versions = relationship("PageVersion", back_populates="page", cascade="all, delete-orphan")

# class PageVersion(Base, TimestampedModel):
#     """Version history for static pages"""
    
#     __tablename__ = "page_versions"
    
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     page_id = Column(UUID(as_uuid=True), ForeignKey("static_pages.id", ondelete="CASCADE"), nullable=False)
#     version_number = Column(Integer, nullable=False)
#     title = Column(String(200), nullable=False)
#     content = Column(Text, nullable=False)
#     change_summary = Column(Text)
#     created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
#     # Relationships
#     page = relationship("StaticPage", back_populates="versions")
#     creator = relationship("User")
