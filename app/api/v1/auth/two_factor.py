"""Two-factor authentication routes"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.two_factor import TwoFactorService

router = APIRouter()

@router.post("/2fa/setup")
async def setup_2fa(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Setup 2FA for user"""
    service = TwoFactorService()
    
    # Generate secret
    secret = service.generate_secret()
    
    # Get user
    from app.models import User
    user = await db.get(User, current_user["id"])
    
    # Generate QR code
    qr_code = service.generate_qr_code(user, secret)
    
    # Generate backup codes
    backup_codes = await service.generate_backup_codes(user.id)
    
    return {
        "secret": secret,
        "qr_code": qr_code,
        "backup_codes": backup_codes
    }

@router.post("/2fa/enable")
async def enable_2fa(
    secret: str,
    token: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Enable 2FA after verification"""
    service = TwoFactorService()
    
    # Verify token
    if not service.verify_token(secret, token):
        raise HTTPException(status_code=400, detail="Invalid token")
        
    # Update user
    from sqlalchemy import update
    from app.models import User
    
    await db.execute(
        update(User)
        .where(User.id == current_user["id"])
        .values(two_factor_secret=secret, two_factor_enabled=True)
    )
    await db.commit()
    
    return {"message": "2FA enabled successfully"}

@router.post("/2fa/verify")
async def verify_2fa(
    token: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify 2FA token"""
    from app.models import User
    user = await db.get(User, current_user["id"])
    
    if not user.two_factor_enabled:
        raise HTTPException(status_code=400, detail="2FA not enabled")
        
    service = TwoFactorService()
    
    # Try regular token first
    if service.verify_token(user.two_factor_secret, token):
        return {"valid": True}
        
    # Try backup code
    if await service.verify_backup_code(user.id, token):
        return {"valid": True, "backup_code_used": True}
        
    raise HTTPException(status_code=400, detail="Invalid token")

@router.post("/2fa/disable")
async def disable_2fa(
    password: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Disable 2FA"""
    from sqlalchemy import update
    from app.models import User
    
    # Verify password
    user = await db.get(User, current_user["id"])
    # Add password verification logic here
    
    await db.execute(
        update(User)
        .where(User.id == current_user["id"])
        .values(two_factor_secret=None, two_factor_enabled=False)
    )
    await db.commit()
    
    return {"message": "2FA disabled successfully"}
