"""WebSocket route handlers"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional
import json
import logging

from app.core.database import get_db
from app.core.websocket import manager, get_current_user_ws
from app.models.order import Order
from app.models.chat import ChatRoom, ChatMessage, ChatParticipant
from app.models.user import User
from app.services.chat_service import ChatService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/orders/{order_id}")
async def track_order(
    websocket: WebSocket,
    order_id: str,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Live order tracking WebSocket"""
    user_id = await get_current_user_ws(websocket, token)
    if not user_id:
        return
        
    # Verify user has access to this order
    order = await db.get(Order, order_id)
    if not order or (order.buyer_id != user_id and order.seller_id != user_id):
        await websocket.close(code=1008, reason="Unauthorized")
        return
        
    await manager.connect(websocket, user_id)
    
    # Join order-specific room
    order_room = f"order:{order_id}"
    await manager.join_room(user_id, order_room)
    
    try:
        # Send initial order status
        await websocket.send_json({
            "type": "order_status",
            "data": {
                "order_id": str(order.id),
                "status": order.status,
                "tracking_number": order.tracking_number,
                "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
                "current_location": order.current_location
            }
        })
        
        while True:
            # Keep connection alive
            data = await websocket.receive_json()
            
            if data["type"] == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        await manager.leave_room(user_id, order_room)
        manager.disconnect(websocket, user_id)

@router.websocket("/ws/chat/{room_id}")
async def chat_websocket(
    websocket: WebSocket,
    room_id: str,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Seller-buyer chat WebSocket"""
    user_id = await get_current_user_ws(websocket, token)
    if not user_id:
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
        await websocket.close(code=1008, reason="Not a participant")
        return
        
    await manager.connect(websocket, user_id)
    await manager.join_room(user_id, f"chat:{room_id}")
    
    chat_service = ChatService(db)
    
    try:
        # Send recent messages
        recent_messages = await chat_service.get_recent_messages(room_id, limit=50)
        await websocket.send_json({
            "type": "message_history",
            "messages": [msg.dict() for msg in recent_messages]
        })
        
        # Mark messages as read
        await chat_service.mark_messages_read(room_id, user_id)
        
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "message":
                # Save message
                message = await chat_service.send_message(
                    room_id=room_id,
                    sender_id=user_id,
                    content=data["content"],
                    message_type=data.get("message_type", "text")
                )
                
                # Broadcast to room
                await manager.broadcast_to_room(f"chat:{room_id}", {
                    "type": "new_message",
                    "message": {
                        "id": str(message.id),
                        "sender_id": str(message.sender_id),
                        "content": message.content,
                        "message_type": message.message_type,
                        "created_at": message.created_at.isoformat()
                    }
                })
                
            elif data["type"] == "typing":
                # Broadcast typing indicator
                await manager.broadcast_to_room(f"chat:{room_id}", {
                    "type": "typing",
                    "user_id": user_id,
                    "is_typing": data.get("is_typing", False)
                }, exclude_user=user_id)
                
            elif data["type"] == "read_receipt":
                # Update read status
                await chat_service.mark_messages_read(room_id, user_id)
                
    except WebSocketDisconnect:
        await manager.leave_room(user_id, f"chat:{room_id}")
        manager.disconnect(websocket, user_id)

@router.websocket("/ws/admin/notifications")
async def admin_notifications(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Admin notification WebSocket"""
    user_id = await get_current_user_ws(websocket, token)
    if not user_id:
        return
        
    # Verify user is admin
    user = await db.get(User, user_id)
    if not user or user.role != "admin":
        await websocket.close(code=1008, reason="Admin access required")
        return
        
    await manager.connect(websocket, user_id)
    await manager.join_room(user_id, "admin:notifications")
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "ping":
                await websocket.send_json({"type": "pong"})
                
            elif data["type"] == "subscribe":
                # Subscribe to specific notification types
                notification_types = data.get("types", [])
                for notif_type in notification_types:
                    await manager.join_room(user_id, f"admin:{notif_type}")
                    
    except WebSocketDisconnect:
        await manager.leave_room(user_id, "admin:notifications")
        manager.disconnect(websocket, user_id)
