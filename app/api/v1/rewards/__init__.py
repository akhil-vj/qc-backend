"""Rewards API router"""

from fastapi import APIRouter
from .router import router as rewards_router

router = APIRouter(prefix="/rewards", tags=["rewards"])
router.include_router(rewards_router)
