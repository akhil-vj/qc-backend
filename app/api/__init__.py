"""API initialization with versioning"""

from fastapi import APIRouter, Request
from .versioning import VersionedAPI

# Initialize versioned API
api = VersionedAPI()

# Import v1 routes
from .v1 import router as v1_router
api.register_version("v1", v1_router)

# Create main router
router = APIRouter()

@router.api_route("/{version}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def versioned_api(version: str, request: Request):
    """Route to appropriate API version"""
    version_router = api.get_router(version)
    return await version_router(request)
