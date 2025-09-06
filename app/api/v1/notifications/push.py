"""Push notification endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, List
import uuid

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.services.push_notifications import PushNotificationService
from .schemas import (
    DeviceTokenRequest, NotificationRequest, BroadcastRequest,
    TopicSubscriptionRequest, NotificationResponse
)

router = APIRouter()

@router.post("/device-token/register")
async def register_device_token(
    request: DeviceTokenRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Register device token for push notifications"""
    service = PushNotificationService(db)
    
    await service.register_device_token(
        user_id=current_user["id"],
        token=request.token,
        device_type=request.device_type,
        device_info=request.device_info
    )
    
    return {"message": "Device token registered successfully"}

@router.delete("/device-token/{token}")
async def remove_device_token(
    token: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove device token"""
    from app.models import DeviceToken
    
    result = await db.execute(
        select(DeviceToken).where(
            and_(
                DeviceToken.token == token,
                DeviceToken.user_id == current_user["id"]
            )
        )
    )
    device_token = result.scalar()
    
    if device_token:
        await db.delete(device_token)
        await db.commit()
        
    return {"message": "Device token removed"}

@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    request: NotificationRequest,
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Send notification to specific user (admin only)"""
    service = PushNotificationService(db)
    
    result = await service.send_to_user(
        user_id=request.user_id,
        title=request.title,
        body=request.body,
        data=request.data,
        image_url=request.image_url,
        action_url=request.action_url
    )
    
    return result

@router.post("/broadcast", response_model=NotificationResponse)
async def broadcast_notification(
    request: BroadcastRequest,
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Broadcast notification to multiple users (admin only)"""
    service = PushNotificationService(db)
    
    result = await service.send_broadcast(
        title=request.title,
        body=request.body,
        user_filters=request.user_filters,
        data=request.data,
        image_url=request.image_url
    )
    
    return result

@router.post("/topics/subscribe")
async def subscribe_to_topic(
    request: TopicSubscriptionRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Subscribe to notification topic"""
    service = PushNotificationService(db)
    
    # Validate topic
    allowed_topics = ["flash_sales", "promotions", "new_products", "order_updates"]
    if request.topic not in allowed_topics:
        raise HTTPException(status_code=400, detail="Invalid topic")
        
    result = await service.subscribe_to_topic(
        user_id=current_user["id"],
        topic=request.topic
    )
    
    return result

@router.post("/topics/unsubscribe")
async def unsubscribe_from_topic(
    request: TopicSubscriptionRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Unsubscribe from notification topic"""
    service = PushNotificationService(db)
    
    result = await service.unsubscribe_from_topic(
        user_id=current_user["id"],
        topic=request.topic
    )
    
    return result

@router.get("/topics")
async def get_subscribed_topics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's subscribed topics"""
    user = await db.get(User, current_user["id"])
    
    return {
        "topics": user.notification_topics or [],
        "available_topics": [
            {
                "id": "flash_sales",
                "name": "Flash Sales",
                "description": "Get notified about limited-time deals"
            },
            {
                "id": "promotions",
                "name": "Promotions",
                "description": "Exclusive offers and discounts"
            },
            {
                "id": "new_products",
                "name": "New Products",
                "description": "Latest products in your favorite categories"
            },
            {
                "id": "order_updates",
                "name": "Order Updates",
                "description": "Real-time order status updates"
            }
        ]
    }

@router.post("/test", dependencies=[Depends(require_admin)])
async def test_notification(
    user_id: str = Body(...),
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Test notification to specific user (admin only)"""
    service = PushNotificationService(db)
    
    result = await service.send_to_user(
        user_id=user_id,
        title="Test Notification",
        body="This is a test notification from QuickCart",
        data={"type": "test"}
    )
    
    return result
