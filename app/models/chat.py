"""Chat models"""

from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Enum, JSON, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from app.models.base import Base, TimestampedModel

class RoomType(str, enum.Enum):
    PRIVATE = "private"
    GROUP = "group"
    SUPPORT = "support"
    ORDER = "order"

class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"

class ChatRoom(Base, TimestampedModel):
    """Chat room model"""
    
    __tablename__ = "chat_rooms"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200))
    room_type = Column(Enum(RoomType), default=RoomType.PRIVATE)
    is_active = Column(Boolean, default=True)
    room_metadata = Column(JSON, default={})
    
    # Relationships
    participants = relationship("ChatParticipant", back_populates="room", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")

class ChatParticipant(Base, TimestampedModel):
    """Chat room participants"""
    
    __tablename__ = "chat_participants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(UUID(as_uuid=True), ForeignKey("chat_rooms.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_admin = Column(Boolean, default=False)
    last_read_at = Column(DateTime(timezone=True))
    
    # Relationships
    room = relationship("ChatRoom", back_populates="participants")
    user = relationship("User")
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint("room_id", "user_id"),
    )

class ChatMessage(Base, TimestampedModel):
    """Chat messages"""
    
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(UUID(as_uuid=True), ForeignKey("chat_rooms.id"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(Enum(MessageType), default=MessageType.TEXT)
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime(timezone=True))
    message_metadata = Column(JSON, default={})
    
    # Relationships
    room = relationship("ChatRoom", back_populates="messages")
    sender = relationship("User")




# """
# Chat and messaging models
# """

# from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Index
# from sqlalchemy.dialects.postgresql import UUID, JSONB
# from sqlalchemy.orm import relationship
# import uuid

# from .base import Base, TimestampedModel

# class Conversation(Base, TimestampedModel):
#     """Chat conversations between users"""
    
#     __tablename__ = "conversations"
    
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
#     # Participants
#     buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
#     seller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
#     # Related entities
#     product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
#     order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    
#     # Status
#     is_active = Column(Boolean, default=True)
#     closed_at = Column(DateTime(timezone=True), nullable=True)
#     closed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
#     # Last message preview
#     last_message = Column(Text, nullable=True)
#     last_message_at = Column(DateTime(timezone=True), nullable=True)
    
#     # Unread counts
#     buyer_unread_count = Column(Integer, default=0)
#     seller_unread_count = Column(Integer, default=0)
    
#     # Relationships
#     buyer = relationship("User", foreign_keys=[buyer_id])
#     seller = relationship("User", foreign_keys=[seller_id])
#     product = relationship("Product")
#     order = relationship("Order")
#     messages = relationship("ChatMessage", back_populates="conversation")
    
#     # Indexes
#     __table_args__ = (
#         Index("idx_conversations_buyer", "buyer_id"),
#         Index("idx_conversations_seller", "seller_id"),
#         Index("idx_conversations_active", "is_active"),
#     )

# class ChatMessage(Base, TimestampedModel):
#     """Individual chat messages"""
    
#     __tablename__ = "chat_messages"
    
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
#     sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
#     # Message content
#     message = Column(Text, nullable=False)
#     message_type = Column(String(50), default="text")  # text, image, product, order
    
#     # Attachments
#     attachments = Column(JSONB, default=[])
    
#     # Status
#     is_read = Column(Boolean, default=False)
#     read_at = Column(DateTime(timezone=True), nullable=True)
    
#     # Moderation
#     is_flagged = Column(Boolean, default=False)
#     flagged_reason = Column(String(255), nullable=True)
    
#     # Relationships
#     conversation = relationship("Conversation", back_populates="messages")
#     sender = relationship("User")
    
#     # Indexes
#     __table_args__ = (
#         Index("idx_chat_messages_conversation", "conversation_id"),
#         Index("idx_chat_messages_created", "created_at"),
#     )
