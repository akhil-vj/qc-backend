"""WebSocket connection manager and handlers"""

from typing import Dict, List, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, status, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import json
import logging
from datetime import datetime
import uuid

from app.core.database import get_db
from app.core.security import SecurityUtils
from app.models.user import User
from app.models.chat import ChatMessage, ChatRoom, ChatParticipant

logger = logging.getLogger(__name__)

# Create WebSocket router
router = APIRouter(prefix="/websocket", tags=["websocket"])

class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        # Active connections: {user_id: [websocket1, websocket2]}
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Room subscriptions: {room_id: {user_ids}}
        self.room_subscriptions: Dict[str, Set[str]] = {}
        # User to rooms mapping: {user_id: {room_ids}}
        self.user_rooms: Dict[str, Set[str]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept new connection"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        
        logger.info(f"User {user_id} connected via WebSocket")
        
        # Send connection success
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove connection"""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
        logger.info(f"User {user_id} disconnected from WebSocket")
        
    async def send_personal_message(self, user_id: str, message: dict):
        """Send message to specific user"""
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)
                    
            # Clean up disconnected sockets
            for conn in disconnected:
                self.active_connections[user_id].remove(conn)
                
    async def broadcast_to_room(self, room_id: str, message: dict, exclude_user: Optional[str] = None):
        """Broadcast message to all users in a room"""
        if room_id in self.room_subscriptions:
            for user_id in self.room_subscriptions[room_id]:
                if user_id != exclude_user:
                    await self.send_personal_message(user_id, message)
                    
    async def join_room(self, user_id: str, room_id: str):
        """Add user to a room"""
        if room_id not in self.room_subscriptions:
            self.room_subscriptions[room_id] = set()
        self.room_subscriptions[room_id].add(user_id)
        
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()
        self.user_rooms[user_id].add(room_id)
        
        # Notify room members
        await self.broadcast_to_room(room_id, {
            "type": "user_joined",
            "room_id": room_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }, exclude_user=user_id)
        
    async def leave_room(self, user_id: str, room_id: str):
        """Remove user from a room"""
        if room_id in self.room_subscriptions:
            self.room_subscriptions[room_id].discard(user_id)
            if not self.room_subscriptions[room_id]:
                del self.room_subscriptions[room_id]
                
        if user_id in self.user_rooms:
            self.user_rooms[user_id].discard(room_id)
            
        # Notify room members
        await self.broadcast_to_room(room_id, {
            "type": "user_left",
            "room_id": room_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    async def send_notification(self, user_id: str, notification: dict):
        """Send notification to user"""
        message = {
            "type": "notification",
            "data": notification,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_personal_message(user_id, message)
        
    async def broadcast_notification(self, user_ids: List[str], notification: dict):
        """Send notification to multiple users"""
        message = {
            "type": "notification",
            "data": notification,
            "timestamp": datetime.utcnow().isoformat()
        }
        for user_id in user_ids:
            await self.send_personal_message(user_id, message)

# Global connection manager
manager = ConnectionManager()

async def get_current_user_ws(
    websocket: WebSocket,
    token: Optional[str] = None
) -> Optional[str]:
    """Authenticate WebSocket connection"""
    if not token:
        # Try to get token from query params
        token = websocket.query_params.get("token")
        
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
        
    try:
        payload = SecurityUtils.decode_token(token)
        return payload.get("sub")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db)
):
    """Main WebSocket endpoint"""
    user_id = await get_current_user_ws(websocket)
    if not user_id:
        return
        
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            # Handle different message types
            if data["type"] == "ping":
                await websocket.send_json({"type": "pong"})
                
            elif data["type"] == "join_room":
                room_id = data.get("room_id")
                if room_id:
                    await manager.join_room(user_id, room_id)
                    
            elif data["type"] == "leave_room":
                room_id = data.get("room_id")
                if room_id:
                    await manager.leave_room(user_id, room_id)
                    
            elif data["type"] == "chat_message":
                await handle_chat_message(user_id, data, db)
                
            elif data["type"] == "typing":
                await handle_typing_indicator(user_id, data)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        manager.disconnect(websocket, user_id)

async def handle_chat_message(user_id: str, data: dict, db: AsyncSession):
    """Handle incoming chat message"""
    room_id = data.get("room_id")
    content = data.get("content")
    
    if not room_id or not content:
        return
        
    # Verify user is participant
    participant = await db.execute(
        select(ChatParticipant).where(
            and_(
                ChatParticipant.room_id == room_id,
                ChatParticipant.user_id == user_id
            )
        )
    )
    if not participant.scalar_one_or_none():
        return
        
    # Create message
    message = ChatMessage(
        room_id=room_id,
        sender_id=user_id,
        content=content,
        message_type=data.get("message_type", "text")
    )
    
    db.add(message)
    await db.commit()
    
    # Broadcast to room
    await manager.broadcast_to_room(room_id, {
        "type": "chat_message",
        "room_id": room_id,
        "message": {
            "id": str(message.id),
            "sender_id": user_id,
            "content": content,
            "message_type": message.message_type,
            "created_at": message.created_at.isoformat()
        }
    })

async def handle_typing_indicator(user_id: str, data: dict):
    """Handle typing indicator"""
    room_id = data.get("room_id")
    is_typing = data.get("is_typing", False)
    
    if not room_id:
        return
        
    await manager.broadcast_to_room(room_id, {
        "type": "typing",
        "room_id": room_id,
        "user_id": user_id,
        "is_typing": is_typing
    }, exclude_user=user_id)
