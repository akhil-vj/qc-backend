from fastapi import APIRouter

router = APIRouter()

@router.get("/pages")
async def get_pages():
    """Get CMS pages"""
    return {"pages": []}

@router.get("/health")
async def cms_health_check():
    """CMS service health check"""
    return {"status": "healthy", "service": "cms"}
