"""Admin moderation endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from app.core.database import get_db
from app.core.security import require_admin
from app.models import Report, Product, User, Review, Badge, UserBadge
from .schemas import (
    ReportResponse, ResolveReportRequest, ModerateContentRequest,
    BadgeCreate, BadgeAssignment, ModerationAction
)

router = APIRouter()

@router.get("/reports", response_model=List[ReportResponse])
async def get_all_reports(
    status: Optional[str] = Query(None, description="Filter by status: pending, resolved, rejected"),
    content_type: Optional[str] = Query(None, description="Filter by type: product, review, user"),
    page: int = Query(1, ge=1),
    size: int = Query(20, le=100),
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all reported content with filters"""
    query = select(Report).options(
        selectinload(Report.reporter),
        selectinload(Report.product),
        selectinload(Report.review),
        selectinload(Report.reported_user)
    )
    
    # Apply filters
    conditions = []
    if status:
        conditions.append(Report.status == status)
    if content_type:
        conditions.append(Report.content_type == content_type)
        
    if conditions:
        query = query.where(and_(*conditions))
        
    # Count total
    count_query = select(func.count()).select_from(Report)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = await db.scalar(count_query)
    
    # Paginate
    query = query.order_by(Report.created_at.desc())
    query = query.offset((page - 1) * size).limit(size)
    
    result = await db.execute(query)
    reports = result.scalars().all()
    
    return {
        "items": reports,
        "total": total,
        "page": page,
        "pages": (total + size - 1) // size
    }

@router.put("/reports/{report_id}/resolve")
async def resolve_report(
    report_id: uuid.UUID,
    request: ResolveReportRequest,
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Resolve a report with action"""
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    # Update report status
    report.status = request.status
    report.resolution = request.resolution
    report.resolved_by = current_admin["id"]
    report.resolved_at = datetime.utcnow()
    report.admin_notes = request.notes
    
    # Take action based on resolution
    if request.action:
        await _take_moderation_action(
            db,
            report,
            request.action,
            request.action_duration_days,
            current_admin["id"]
        )
    
    await db.commit()
    
    # Send notification to reporter
    from app.services.notification import NotificationService
    notification_service = NotificationService(db)
    await notification_service.create_notification(
        user_id=report.reporter_id,
        title="Report Update",
        message=f"Your report has been {request.status}",
        type="report_update",
        metadata={"report_id": str(report_id)}
    )
    
    return {"message": "Report resolved successfully"}

@router.post("/moderate/{content_type}/{content_id}")
async def moderate_content(
    content_type: str,
    content_id: uuid.UUID,
    request: ModerateContentRequest,
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Directly moderate content without report"""
    if content_type not in ["product", "review", "user"]:
        raise HTTPException(status_code=400, detail="Invalid content type")
        
    # Create moderation log
    from app.models import ModerationLog
    moderation_log = ModerationLog(
        admin_id=current_admin["id"],
        content_type=content_type,
        content_id=content_id,
        action=request.action,
        reason=request.reason,
        duration_days=request.duration_days
    )
    db.add(moderation_log)
    
    # Take action
    if content_type == "product":
        await _moderate_product(db, content_id, request.action, request.duration_days)
    elif content_type == "review":
        await _moderate_review(db, content_id, request.action)
    elif content_type == "user":
        await _moderate_user(db, content_id, request.action, request.duration_days)
        
    await db.commit()
    
    return {"message": f"{content_type} moderated successfully"}

@router.get("/badges", response_model=List[Badge])
async def get_all_badges(
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all available badges"""
    result = await db.execute(select(Badge).order_by(Badge.created_at.desc()))
    return result.scalars().all()

@router.post("/badges", response_model=Badge)
async def create_badge(
    badge: BadgeCreate,
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new badge"""
    db_badge = Badge(**badge.dict())
    db.add(db_badge)
    await db.commit()
    await db.refresh(db_badge)
    return db_badge

@router.post("/badges/assign")
async def assign_badge(
    assignment: BadgeAssignment,
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Assign badge to user/seller/brand"""
    # Check if badge exists
    badge = await db.get(Badge, assignment.badge_id)
    if not badge:
        raise HTTPException(status_code=404, detail="Badge not found")
        
    # Check if already assigned
    existing = await db.execute(
        select(UserBadge).where(
            and_(
                UserBadge.user_id == assignment.user_id,
                UserBadge.badge_id == assignment.badge_id
            )
        )
    )
    if existing.scalar():
        raise HTTPException(status_code=400, detail="Badge already assigned")
        
    # Assign badge
    user_badge = UserBadge(
        user_id=assignment.user_id,
        badge_id=assignment.badge_id,
        assigned_by=current_admin["id"],
        expires_at=assignment.expires_at,
        metadata=assignment.metadata
    )
    db.add(user_badge)
    
    # Send notification
    from app.services.notification import NotificationService
    notification_service = NotificationService(db)
    await notification_service.create_notification(
        user_id=assignment.user_id,
        title="New Badge Earned!",
        message=f"You've been awarded the '{badge.name}' badge!",
        type="badge_earned",
        metadata={"badge_id": str(badge.id), "badge_name": badge.name}
    )
    
    await db.commit()
    
    return {"message": "Badge assigned successfully"}

@router.delete("/badges/{user_id}/{badge_id}")
async def revoke_badge(
    user_id: uuid.UUID,
    badge_id: uuid.UUID,
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Revoke a badge from user"""
    result = await db.execute(
        select(UserBadge).where(
            and_(
                UserBadge.user_id == user_id,
                UserBadge.badge_id == badge_id
            )
        )
    )
    user_badge = result.scalar()
    
    if not user_badge:
        raise HTTPException(status_code=404, detail="Badge assignment not found")
        
    await db.delete(user_badge)
    await db.commit()
    
    return {"message": "Badge revoked successfully"}

# Helper functions
async def _take_moderation_action(
    db: AsyncSession,
    report: Report,
    action: str,
    duration_days: Optional[int],
    admin_id: str
):
    """Execute moderation action based on report"""
    if report.content_type == "product":
        await _moderate_product(db, report.product_id, action, duration_days)
    elif report.content_type == "review":
        await _moderate_review(db, report.review_id, action)
    elif report.content_type == "user":
        await _moderate_user(db, report.reported_user_id, action, duration_days)

async def _moderate_product(
    db: AsyncSession,
    product_id: uuid.UUID,
    action: str,
    duration_days: Optional[int] = None
):
    """Moderate a product"""
    product = await db.get(Product, product_id)
    if not product:
        return
        
    if action == "hold":
        product.status = "on_hold"
        if duration_days:
            product.hold_until = datetime.utcnow() + timedelta(days=duration_days)
    elif action == "ban":
        product.status = "banned"
    elif action == "approve":
        product.status = "active"
        product.hold_until = None

async def _moderate_review(
    db: AsyncSession,
    review_id: uuid.UUID,
    action: str
):
    """Moderate a review"""
    review = await db.get(Review, review_id)
    if not review:
        return
        
    if action == "hide":
        review.is_hidden = True
    elif action == "delete":
        await db.delete(review)
    elif action == "approve":
        review.is_hidden = False

async def _moderate_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    action: str,
    duration_days: Optional[int] = None
):
    """Moderate a user"""
    user = await db.get(User, user_id)
    if not user:
        return
        
    if action == "suspend":
        user.is_suspended = True
        if duration_days:
            user.suspended_until = datetime.utcnow() + timedelta(days=duration_days)
    elif action == "ban":
        user.is_banned = True
    elif action == "unban":
        user.is_banned = False
        user.is_suspended = False
        user.suspended_until = None
