"""Audit logging service"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request
import uuid

from app.models.admin_log import AdminLog

class AuditService:
    """Service for logging admin actions"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def log_admin_action(
        self,
        admin_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        description: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None
    ) -> AdminLog:
        """Log an admin action"""
        # Extract request info if available
        ip_address = None
        user_agent = None
        
        if request:
            # Get IP address
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                ip_address = forwarded.split(",")[0]
            else:
                ip_address = request.client.host
                
            # Get user agent
            user_agent = request.headers.get("User-Agent")
            
        # Create log entry
        log = AdminLog(
            admin_id=admin_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            description=description,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.db.add(log)
        await self.db.commit()
        
        return log
        
    async def get_admin_logs(
        self,
        admin_id: Optional[str] = None,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AdminLog]:
        """Get admin logs with filters"""
        from sqlalchemy import select
        
        stmt = select(AdminLog)
        
        if admin_id:
            stmt = stmt.where(AdminLog.admin_id == admin_id)
        if action:
            stmt = stmt.where(AdminLog.action == action)
        if entity_type:
            stmt = stmt.where(AdminLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AdminLog.entity_id == str(entity_id))
            
        stmt = stmt.order_by(AdminLog.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
