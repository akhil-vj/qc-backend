from fastapi import APIRouter

router = APIRouter()

@router.get("/balance")
async def get_coin_balance():
    """Get user coin balance"""
    return {"balance": 0}

@router.get("/transactions")
async def get_coin_transactions():
    """Get coin transaction history"""
    return {"transactions": []}

@router.get("/health")
async def coins_health_check():
    """Coins service health check"""
    return {"status": "healthy", "service": "coins"}
