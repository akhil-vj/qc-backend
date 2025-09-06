"""API versioning system"""

from fastapi import APIRouter, Request, HTTPException
from typing import Callable, Optional

class VersionedAPI:
    """Handle API versioning"""
    
    def __init__(self):
        self.versions = {}
        self.latest_version = None
        
    def register_version(self, version: str, router: APIRouter):
        """Register a new API version"""
        self.versions[version] = router
        self.latest_version = version
        
    def get_router(self, version: Optional[str] = None) -> APIRouter:
        """Get router for specific version"""
        if version is None:
            version = self.latest_version
            
        if version not in self.versions:
            raise HTTPException(
                status_code=400,
                detail=f"API version {version} not supported"
            )
            
        return self.versions[version]
        
    def deprecate_version(self, version: str, sunset_date: str):
        """Mark version as deprecated"""
        def middleware(request: Request, call_next: Callable):
            response = call_next(request)
            response.headers["Sunset"] = sunset_date
            response.headers["Deprecation"] = "true"
            return response
            
        return middleware
