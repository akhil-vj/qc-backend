"""Admin moderation schemas"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
import uuid

class AdminStats(BaseModel):
    total_users: int
    total_orders: int
    total_revenue: float
    total_products: int
    active_sellers: Optional[int] = 0
    pending_seller_applications: Optional[int] = 0
    support_tickets_open: Optional[int] = 0
    total_sales_today: Optional[float] = 0.0
    new_users_today: Optional[int] = 0
    orders_today: Optional[int] = 0

class AdminUsersList(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    is_seller: Optional[bool] = False
    created_at: str
    last_login: Optional[str] = None
    total_orders: Optional[int] = 0
    total_spent: Optional[float] = 0.0

class ReportResponse(BaseModel):
    id: uuid.UUID
    reporter_id: uuid.UUID
    reporter_name: str
    content_type: str
    content_id: uuid.UUID
    reason: str
    description: Optional[str]
    status: str
    resolution: Optional[str]
    admin_notes: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]
    
class ResolveReportRequest(BaseModel):
    status: str = Field(..., description="resolved, rejected")
    resolution: str
    notes: Optional[str]
    action: Optional[str] = Field(None, description="hold, ban, delete, approve")
    action_duration_days: Optional[int]
    
class ModerateContentRequest(BaseModel):
    action: str = Field(..., description="hold, ban, delete, hide, approve")
    reason: str
    duration_days: Optional[int]
    
class BadgeCreate(BaseModel):
    name: str
    description: str
    icon: str
    badge_type: str = Field(..., description="user, seller, brand, special")
    criteria: Optional[Dict[str, Any]]
    
class BadgeAssignment(BaseModel):
    user_id: uuid.UUID
    badge_id: uuid.UUID
    expires_at: Optional[datetime]
    metadata: Optional[Dict[str, Any]]
    
class ModerationAction(BaseModel):
    action: str
    reason: str
    duration_days: Optional[int]
