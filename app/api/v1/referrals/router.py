from fastapi import APIRouter

router = APIRouter()

@router.get("/stats")
async def get_referral_stats():
    """Get referral statistics"""
    return {"total_referrals": 0, "total_earnings": 0}

@router.get("/code")
async def get_referral_code():
    """Get user referral code"""
    return {"referral_code": "SAMPLE123"}

@router.get("/health")
async def referrals_health_check():
    """Referrals service health check"""
    return {"status": "healthy", "service": "referrals"}
