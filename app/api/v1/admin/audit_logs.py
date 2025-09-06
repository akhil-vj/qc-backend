"""Admin audit log endpoints"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import require_admin
from app.services.audit_service import AuditService
from app.core.audit_decorator import audit_action

router = APIRouter(prefix="/admin/audit-logs", tags=["admin-audit"])

class AuditLogResponse(BaseModel):
    id: str
    admin_id: str
    admin_name: str
    action: str
    entity_type: str
    entity_id: str
    description: Optional[str]
    old_values: Optional[Dict[str, Any]]
    new_values: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    created_at: datetime

@router.get("", response_model=List[AuditLogResponse])
async def get_audit_logs(
    admin_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, le=200),
    current_admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get admin audit logs"""
    service = AuditService(db)
    
    offset = (page - 1) * size
    
    logs = await service.get_admin_logs(
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=size,
        offset=offset
    )
    
    # Load admin names
    from app.models.user import User
    response = []
    
    for log in logs:
        admin = await db.get(User, log.admin_id)
        response.append({
            "id": str(log.id),
            "admin_id": str(log.admin_id),
            "admin_name": admin.name if admin else "Unknown",
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "description": log.description,
            "old_values": log.old_values,
            "new_values": log.new_values,
            "ip_address": log.ip_address,
            "created_at": log.created_at
        })
        
    return response

# Example usage in other admin endpoints
@router.post("/example/ban-user/{user_id}")
@audit_action(
    action="ban_user",
    entity_type="user",
    entity_id_param="user_id",
    description_template="Banned user {entity_id}"
)
async def ban_user_example(
    user_id: str,
    request: Request,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Example endpoint showing audit logging"""
    # Your ban user logic here
    return {"message": "User banned and action logged"}
