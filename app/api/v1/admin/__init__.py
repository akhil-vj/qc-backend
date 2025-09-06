"""Admin API router"""

from fastapi import APIRouter
from .router import router as admin_router

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(admin_router)
