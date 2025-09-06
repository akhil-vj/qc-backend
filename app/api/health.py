"""Health check and monitoring endpoints"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import psutil
import aioredis
from datetime import datetime

from app.core.database import get_db
from app.core.cache import cache
from app.core.config import settings

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Detailed health check with component status"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }
    
    # Check database
    try:
        await db.execute("SELECT 1")
        health_status["components"]["database"] = {
            "status": "healthy",
            "response_time_ms": 0  # Add actual timing
        }
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
        
    # Check Redis
    try:
        await cache.ping()
        health_status["components"]["redis"] = {
            "status": "healthy"
        }
    except Exception as e:
        health_status["components"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
        
    # Check external services
    health_status["components"]["payment_gateway"] = await check_payment_gateway()
    health_status["components"]["sms_service"] = await check_sms_service()
    
    # System metrics
    health_status["metrics"] = {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent
    }
    
    return health_status

async def check_payment_gateway() -> Dict[str, Any]:
    """Check payment gateway health"""
    # Implement actual health check
    return {"status": "healthy"}

async def check_sms_service() -> Dict[str, Any]:
    """Check SMS service health"""
    # Implement actual health check
    return {"status": "healthy"}

@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Get application metrics for monitoring"""
    metrics = {}
    
    # Database metrics
    db_stats = await db.execute("""
    SELECT 
        (SELECT COUNT(*) FROM users) as total_users,
        (SELECT COUNT(*) FROM products WHERE status = 'active') as active_products,
        (SELECT COUNT(*) FROM orders WHERE created_at > NOW() - INTERVAL '24 hours') as daily_orders,
        (SELECT SUM(total_amount) FROM orders WHERE created_at > NOW() - INTERVAL '24 hours') as daily_revenue
    """)
    
    db_metrics = db_stats.one()
    metrics["database"] = {
        "total_users": db_metrics.total_users,
        "active_products": db_metrics.active_products,
        "daily_orders": db_metrics.daily_orders,
        "daily_revenue": float(db_metrics.daily_revenue or 0)
    }
    
    # Cache metrics
    cache_info = await cache.info()
    metrics["cache"] = {
        "used_memory": cache_info.get("used_memory_human"),
        "connected_clients": cache_info.get("connected_clients"),
        "total_commands_processed": cache_info.get("total_commands_processed")
    }
    
    # Application metrics
    metrics["application"] = {
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": (datetime.utcnow() - settings.STARTUP_TIME).total_seconds()
    }
    
    return metrics
