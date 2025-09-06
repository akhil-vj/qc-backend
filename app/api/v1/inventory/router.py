from fastapi import APIRouter

router = APIRouter()

@router.get("/items")
async def get_inventory_items():
    """Get inventory items"""
    return {"items": []}

@router.get("/health")
async def inventory_health_check():
    """Inventory service health check"""
    return {"status": "healthy", "service": "inventory"}
