"""Seller management endpoints"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.models.user import User

router = APIRouter()

# Admin endpoints for seller management
@router.get("/admin/sellers")
async def list_sellers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """List all sellers with pagination and filtering (Admin only)"""
    try:
        # Mock response for now - would fetch from database
        sellers = [
            {
                "id": 1,
                "name": "Electronics Store",
                "email": "seller1@example.com",
                "status": "active",
                "products_count": 25,
                "total_sales": 15000,
                "rating": 4.5
            },
            {
                "id": 2,
                "name": "Fashion Boutique",
                "email": "seller2@example.com",
                "status": "pending",
                "products_count": 0,
                "total_sales": 0,
                "rating": 0.0
            }
        ]
        return {"sellers": sellers, "total": len(sellers)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch sellers: {str(e)}"
        )

@router.get("/admin/sellers/{seller_id}")
async def get_seller_details(
    seller_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get seller details by ID (Admin only)"""
    try:
        # Mock response - would fetch from database
        seller = {
            "id": seller_id,
            "name": "Electronics Store",
            "email": "seller1@example.com",
            "phone": "+1234567890",
            "address": "123 Business St, City, State",
            "business_license": "BL123456789",
            "status": "active",
            "products_count": 25,
            "total_sales": 15000,
            "rating": 4.5,
            "created_at": "2025-01-01T00:00:00Z",
            "approved_at": "2025-01-02T00:00:00Z"
        }
        return seller
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get seller details: {str(e)}"
        )

@router.post("/admin/sellers/{seller_id}/approve")
async def approve_seller(
    seller_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Approve a seller application (Admin only)"""
    try:
        # Would update seller status in database
        return {"message": "Seller approved successfully", "seller_id": seller_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve seller: {str(e)}"
        )

@router.post("/admin/sellers/{seller_id}/reject")
async def reject_seller(
    seller_id: int,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Reject a seller application (Admin only)"""
    try:
        # Would update seller status and add rejection reason
        return {
            "message": "Seller application rejected",
            "seller_id": seller_id,
            "reason": reason
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject seller: {str(e)}"
        )

@router.post("/admin/sellers/{seller_id}/suspend")
async def suspend_seller(
    seller_id: int,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Suspend a seller account (Admin only)"""
    try:
        # Would update seller status to suspended
        return {
            "message": "Seller suspended successfully",
            "seller_id": seller_id,
            "reason": reason
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to suspend seller: {str(e)}"
        )

# Seller application and profile endpoints
@router.post("/application")
async def submit_seller_application(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit seller application"""
    try:
        # Would create seller application record
        application = {
            "user_id": current_user.id,
            "status": "pending",
            "submitted_at": "2025-08-13T00:00:00Z",
            "message": "Application submitted successfully"
        }
        return application
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit application: {str(e)}"
        )

@router.get("/application/status")
async def get_application_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get seller application status"""
    try:
        # Would fetch from database
        status_info = {
            "status": "pending",
            "submitted_at": "2025-08-13T00:00:00Z",
            "message": "Your application is under review"
        }
        return status_info
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get application status: {str(e)}"
        )

@router.get("/profile")
async def get_seller_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get seller profile"""
    try:
        # Would fetch seller profile from database
        profile = {
            "id": current_user.id,
            "name": "Sample Seller",
            "email": current_user.email,
            "status": "active",
            "products_count": 10,
            "total_sales": 5000,
            "rating": 4.2
        }
        return {"profile": profile}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )

@router.get("/dashboard")
async def get_seller_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get seller dashboard data"""
    try:
        dashboard = {
            "total_products": 25,
            "active_products": 20,
            "pending_orders": 5,
            "total_sales": 15000,
            "monthly_sales": 3000,
            "rating": 4.5,
            "recent_orders": [
                {"id": 1, "amount": 150, "status": "pending"},
                {"id": 2, "amount": 200, "status": "shipped"}
            ]
        }
        return dashboard
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard: {str(e)}"
        )

@router.get("/health")
async def sellers_health_check():
    """Sellers service health check"""
    return {"status": "healthy", "service": "sellers"}
