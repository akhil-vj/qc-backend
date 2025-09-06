"""Enhanced moderation endpoints with audit logging"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.database import get_db
from app.core.security import require_admin
from app.services.audit_service import AuditService

router = APIRouter(prefix="/admin/moderation", tags=["admin-moderation"])

@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: uuid.UUID,
    reason: str,
    request: Request,
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Ban a user with audit logging"""
    from app.models.user import User
    
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    old_values = {"is_banned": user.is_banned, "is_active": user.is_active}
    
    # Ban user
    user.is_banned = True
    user.is_active = False
    
    # Log action
    audit_service = AuditService(db)
    await audit_service.log_admin_action(
        admin_id=current_admin["id"],
        action="ban_user",
        entity_type="user",
        entity_id=str(user_id),
        description=f"Banned user for: {reason}",
        old_values=old_values,
        new_values={"is_banned": True, "is_active": False, "reason": reason},
        request=request
    )
    
    await db.commit()
    
    return {"message": "User banned successfully"}

@router.post("/products/{product_id}/approve")
async def approve_product(
    product_id: uuid.UUID,
    request: Request,
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve a product with audit logging"""
    from app.models.product import Product
    
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    old_status = product.status
    
    # Approve product
    product.status = "active"
    product.approved_at = datetime.utcnow()
    product.approved_by = current_admin["id"]
    
    # Log action
    audit_service = AuditService(db)
    await audit_service.log_admin_action(
        admin_id=current_admin["id"],
        action="approve_product",
        entity_type="product",
        entity_id=str(product_id),
        description=f"Approved product: {product.title}",
        old_values={"status": old_status},
        new_values={"status": "active"},
        request=request
    )
    
    await db.commit()
    
    return {"message": "Product approved successfully"}

@router.post("/users/{user_id}/assign-badge")
async def assign_badge(
    user_id: uuid.UUID,
    badge_id: uuid.UUID,
    request: Request,
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Assign badge to user with audit logging"""
    from app.models.user import User, UserBadge, Badge
    
    user = await db.get(User, user_id)
    badge = await db.get(Badge, badge_id)
    
    if not user or not badge:
        raise HTTPException(status_code=404, detail="User or badge not found")
        
    # Assign badge
    user_badge = UserBadge(
        user_id=user_id,
        badge_id=badge_id,
        assigned_by=current_admin["id"]
    )
    
    db.add(user_badge)
    
    # Log action
    audit_service = AuditService(db)
    await audit_service.log_admin_action(
        admin_id=current_admin["id"],
        action="assign_badge",
        entity_type="user",
        entity_id=str(user_id),
        description=f"Assigned badge '{badge.name}' to user '{user.name}'",
        new_values={"badge_id": str(badge_id), "badge_name": badge.name},
        request=request
    )
    
    await db.commit()
    
    return {"message": "Badge assigned successfully"}
