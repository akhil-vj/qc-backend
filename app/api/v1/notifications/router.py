"""Push notification endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional
from pydantic import BaseModel
import uuid

from app.core.database import get_db
from app.api.v1.auth.dependencies import get_current_user
from app.services.push_notification_service import PushNotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])

class RegisterDeviceTokenRequest(BaseModel):
    token: str
    device_type: str  # ios, android, web
    device_info: Optional[Dict[str, str]] = None

class SendNotificationRequest(BaseModel):
    user_id: str
    title: str
    body: str
    data: Optional[Dict[str, str]] = None
    image_url: Optional[str] = None
    action_url: Optional[str] = None

@router.post("/device-token/register")
async def register_device_token(
    request: RegisterDeviceTokenRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Register FCM device token for push notifications"""
    service = PushNotificationService(db)
    
    await service.register_device_token(
        user_id=current_user["id"],
        token=request.token,
        device_type=request.device_type,
        device_info=request.device_info
    )
    
    return {"message": "Device token registered successfully"}

@router.delete("/device-token/{token}")
async def unregister_device_token(
    token: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Unregister FCM device token"""
    service = PushNotificationService(db)
    
    await service.unregister_device_token(
        token=token,
        user_id=current_user["id"]
    )
    
    return {"message": "Device token unregistered successfully"}

@router.post("/test")
async def send_test_notification(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send test notification to current user"""
    service = PushNotificationService(db)
    
    result = await service.send_to_user(
        user_id=current_user["id"],
        title="Test Notification",
        body="This is a test notification from QuickCart!",
        data={"type": "test"},
        notification_type="test"
    )
    
    return result
