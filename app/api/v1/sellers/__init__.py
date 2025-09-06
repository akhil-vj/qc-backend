"""Sellers API router"""

from fastapi import APIRouter
from .router import router as seller_router

router = APIRouter(prefix="/sellers", tags=["sellers"])
router.include_router(seller_router)
