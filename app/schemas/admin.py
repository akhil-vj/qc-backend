# Placeholder schemas for admin endpoints
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class AdminStats(BaseModel):
    total_users: int
    total_products: int
    total_orders: int
    total_revenue: float
    active_users_today: int
    pending_orders: int

class AdminUsersList(BaseModel):
    items: List[dict]
    total: int
    page: int
    limit: int
    pages: int

class AdminProductsList(BaseModel):
    items: List[dict]
    total: int
    page: int
    limit: int
    pages: int

class AdminOrdersList(BaseModel):
    items: List[dict]
    total: int
    page: int
    limit: int
    pages: int

class AdminUserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None

class AdminSystemSettings(BaseModel):
    site_name: str
    maintenance_mode: bool
    registration_enabled: bool
    email_notifications: bool
