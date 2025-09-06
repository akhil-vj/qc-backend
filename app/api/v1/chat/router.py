"""Chat management endpoints"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.models.user import User

router = APIRouter()

# User chat endpoints
@router.get("/rooms")
async def get_chat_rooms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user chat rooms"""
    try:
        # Mock chat rooms - would fetch from database
        rooms = [
            {
                "id": 1,
                "type": "support",
                "title": "Order Support #1234",
                "participant_count": 2,
                "last_message": "How can I help you today?",
                "last_message_time": "2025-08-13T09:30:00Z",
                "unread_count": 1,
                "status": "active"
            },
            {
                "id": 2,
                "type": "seller",
                "title": "Electronics Store",
                "participant_count": 2,
                "last_message": "Product is available",
                "last_message_time": "2025-08-12T15:45:00Z",
                "unread_count": 0,
                "status": "active"
            }
        ]
        return {"rooms": rooms, "total": len(rooms)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat rooms: {str(e)}"
        )

@router.get("/rooms/{room_id}/messages")
async def get_chat_messages(
    room_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get messages in a chat room"""
    try:
        # Mock messages - would fetch from database
        messages = [
            {
                "id": 1,
                "room_id": room_id,
                "sender_id": 1,
                "sender_name": "Support Agent",
                "message": "Hello! How can I help you today?",
                "message_type": "text",
                "timestamp": "2025-08-13T09:30:00Z",
                "is_read": True
            },
            {
                "id": 2,
                "room_id": room_id,
                "sender_id": current_user.id,
                "sender_name": current_user.email,
                "message": "I have a question about my order",
                "message_type": "text",
                "timestamp": "2025-08-13T09:31:00Z",
                "is_read": True
            }
        ]
        return {"messages": messages, "total": len(messages)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get messages: {str(e)}"
        )

@router.post("/rooms/{room_id}/messages")
async def send_message(
    room_id: int,
    message: str,
    message_type: str = "text",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message to a chat room"""
    try:
        # Mock message sending - would save to database and notify via WebSocket
        new_message = {
            "id": 123,
            "room_id": room_id,
            "sender_id": current_user.id,
            "sender_name": current_user.email,
            "message": message,
            "message_type": message_type,
            "timestamp": "2025-08-13T10:30:00Z",
            "is_read": False
        }
        return {
            "message": "Message sent successfully",
            "message_data": new_message
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )

@router.post("/rooms")
async def create_chat_room(
    chat_type: str,
    participant_id: Optional[int] = None,
    title: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat room"""
    try:
        # Mock room creation - would create in database
        room = {
            "id": 456,
            "type": chat_type,
            "title": title or f"{chat_type.title()} Chat",
            "creator_id": current_user.id,
            "participant_count": 2 if participant_id else 1,
            "created_at": "2025-08-13T10:30:00Z",
            "status": "active"
        }
        return {
            "message": "Chat room created successfully",
            "room": room
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat room: {str(e)}"
        )

@router.put("/rooms/{room_id}/read")
async def mark_room_as_read(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all messages in a room as read"""
    try:
        # Would update message read status in database
        return {"message": "Room marked as read", "room_id": room_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark room as read: {str(e)}"
        )

# Admin chat management endpoints
@router.get("/admin/rooms")
async def get_all_chat_rooms(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    chat_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all chat rooms (Admin only)"""
    try:
        # Mock admin view of all rooms
        rooms = [
            {
                "id": 1,
                "type": "support",
                "title": "Order Support #1234",
                "creator_email": "user1@example.com",
                "participant_count": 2,
                "message_count": 15,
                "created_at": "2025-08-12T10:00:00Z",
                "last_activity": "2025-08-13T09:30:00Z",
                "status": "active"
            },
            {
                "id": 2,
                "type": "seller",
                "title": "Electronics Store",
                "creator_email": "user2@example.com",
                "participant_count": 2,
                "message_count": 8,
                "created_at": "2025-08-11T14:30:00Z",
                "last_activity": "2025-08-12T15:45:00Z",
                "status": "active"
            }
        ]
        return {"rooms": rooms, "total": len(rooms)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat rooms: {str(e)}"
        )

@router.get("/admin/stats")
async def get_chat_stats(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get chat statistics (Admin only)"""
    try:
        stats = {
            "total_rooms": 156,
            "active_rooms": 89,
            "total_messages_today": 342,
            "total_messages_this_week": 1834,
            "average_response_time_minutes": 5.2,
            "support_requests_pending": 12,
            "most_active_hour": "14:00-15:00"
        }
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat stats: {str(e)}"
        )

@router.post("/admin/rooms/{room_id}/close")
async def close_chat_room(
    room_id: int,
    reason: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Close a chat room (Admin only)"""
    try:
        # Would update room status in database
        return {
            "message": "Chat room closed successfully",
            "room_id": room_id,
            "reason": reason,
            "closed_by": current_user.id,
            "closed_at": "2025-08-13T10:30:00Z"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close chat room: {str(e)}"
        )

@router.get("/health")
async def chat_health_check():
    """Chat service health check"""
    return {"status": "healthy", "service": "chat"}
