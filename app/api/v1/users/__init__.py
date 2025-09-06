"""Users API router"""

from fastapi import APIRouter
from .router import router as user_router

router = APIRouter(prefix="/users", tags=["users"])
router.include_router(user_router)
