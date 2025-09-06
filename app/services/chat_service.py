"""Chat service for managing conversations"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from datetime import datetime
import uuid

from app.models.chat import ChatRoom, ChatMessage, ChatParticipant, RoomType, MessageType
from app.models.user import User
from app.models.order import Order

class ChatService:
    """Service for managing chat functionality"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def create_chat_room(
        self,
        participants: List[str],
        room_type: RoomType = RoomType.PRIVATE,
        name: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> ChatRoom:
        """Create a new chat room"""
        room = ChatRoom(
            name=name,
            room_type=room_type,
            metadata=metadata or {}
        )
        self.db.add(room)
        await self.db.flush()
        
        # Add participants
        for user_id in participants:
            participant = ChatParticipant(
                room_id=room.id,
                user_id=user_id,
                is_admin=False
            )
            self.db.add(participant)
            
        await self.db.commit()
        return room
        
    async def get_or_create_order_chat(
        self,
        order_id: str,
        buyer_id: str,
        seller_id: str
    ) -> ChatRoom:
        """Get or create chat room for an order"""
        # Check if room exists
        existing_room = await self.db.execute(
            select(ChatRoom).where(
                and_(
                    ChatRoom.room_type == RoomType.ORDER,
                    ChatRoom.metadata["order_id"].astext == str(order_id)
                )
            )
        )
        
        room = existing_room.scalar_one_or_none()
        if room:
            return room
            
        # Create new room
        return await self.create_chat_room(
            participants=[buyer_id, seller_id],
            room_type=RoomType.ORDER,
            name=f"Order Chat - {order_id[:8]}",
            metadata={"order_id": str(order_id)}
        )
        
    async def send_message(
        self,
        room_id: str,
        sender_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[dict] = None
    ) -> ChatMessage:
        """Send a message in a chat room"""
        message = ChatMessage(
            room_id=room_id,
            sender_id=sender_id,
            content=content,
            message_type=message_type,
            metadata=metadata or {}
        )
        
        self.db.add(message)
        await self.db.commit()
        
        # Update participant's last read time
        await self.db.execute(
            update(ChatParticipant)
            .where(
                and_(
                    ChatParticipant.room_id == room_id,
                    ChatParticipant.user_id == sender_id
                )
            )
            .values(last_read_at=datetime.utcnow())
        )
        
        await self.db.commit()
        return message
        
    async def get_recent_messages(
        self,
        room_id: str,
        limit: int = 50,
        before_id: Optional[str] = None
    ) -> List[ChatMessage]:
        """Get recent messages from a room"""
        query = select(ChatMessage).where(ChatMessage.room_id == room_id)
        
        if before_id:
            query = query.where(ChatMessage.id < before_id)
            
        query = query.order_by(desc(ChatMessage.created_at)).limit(limit)
        
        result = await self.db.execute(query)
        messages = result.scalars().all()
        
        # Return in chronological order
        return list(reversed(messages))
        
    async def mark_messages_read(self, room_id: str, user_id: str):
        """Mark all messages as read for a user"""
        await self.db.execute(
            update(ChatParticipant)
            .where(
                and_(
                    ChatParticipant.room_id == room_id,
                    ChatParticipant.user_id == user_id
                )
            )
            .values(last_read_at=datetime.utcnow())
        )
        await self.db.commit()
        
    async def get_unread_count(self, room_id: str, user_id: str) -> int:
        """Get unread message count for a user in a room"""
        # Get participant's last read time
        participant = await self.db.execute(
            select(ChatParticipant).where(
                and_(
                    ChatParticipant.room_id == room_id,
                    ChatParticipant.user_id == user_id
                )
            )
        )
        
        participant = participant.scalar_one_or_none()
        if not participant:
            return 0
            
        # Count messages after last read
        query = select(func.count(ChatMessage.id)).where(
            and_(
                ChatMessage.room_id == room_id,
                ChatMessage.sender_id != user_id,
                ChatMessage.created_at > (participant.last_read_at or datetime.min)
            )
        )
        
        result = await self.db.execute(query)
        return result.scalar() or 0
