"""Cleanup and maintenance tasks"""

from celery.utils.log import get_task_logger
from datetime import datetime, timedelta

from app.core.celery_app import celery_app
from app.core.database import get_db_sync

logger = get_task_logger(__name__)

@celery_app.task(name="cleanup_expired_tokens")
def cleanup_expired_tokens():
    """Remove expired authentication tokens"""
    try:
        db = next(get_db_sync())
        
        # Clean up expired OTP tokens
        query = """
        DELETE FROM otp_tokens
        WHERE expires_at < NOW()
        """
        result = db.execute(query)
        otp_count = result.rowcount
        
        # Clean up expired refresh tokens
        query = """
        DELETE FROM refresh_tokens
        WHERE expires_at < NOW()
        """
        result = db.execute(query)
        refresh_count = result.rowcount
        
        db.commit()
        
        logger.info(f"Cleaned up {otp_count} OTP tokens and {refresh_count} refresh tokens")
        
        return {
            "otp_tokens_deleted": otp_count,
            "refresh_tokens_deleted": refresh_count
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up tokens: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="cleanup_old_notifications")
def cleanup_old_notifications(days: int = 30):
    """Remove old read notifications"""
    try:
        db = next(get_db_sync())
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = """
        DELETE FROM notifications
        WHERE is_read = TRUE
        AND created_at < :cutoff_date
        """
        
        result = db.execute(query, {"cutoff_date": cutoff_date})
        deleted_count = result.rowcount
        
        db.commit()
        
        logger.info(f"Deleted {deleted_count} old notifications")
        
        return {"deleted_count": deleted_count}
        
    except Exception as e:
        logger.error(f"Error cleaning up notifications: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="archive_old_orders")
def archive_old_orders(months: int = 12):
    """Archive orders older than specified months"""
    try:
        db = next(get_db_sync())
        
        cutoff_date = datetime.utcnow() - timedelta(days=months * 30)
        
        # Move to archive table
        query = """
        INSERT INTO archived_orders
        SELECT * FROM orders
        WHERE created_at < :cutoff_date
        AND status IN ('delivered', 'cancelled')
        """
        
        result = db.execute(query, {"cutoff_date": cutoff_date})
        archived_count = result.rowcount
        
        # Delete from main table
        query = """
        DELETE FROM orders
        WHERE created_at < :cutoff_date
        AND status IN ('delivered', 'cancelled')
        """
        
        db.execute(query, {"cutoff_date": cutoff_date})
        db.commit()
        
        logger.info(f"Archived {archived_count} old orders")
        
        return {"archived_count": archived_count}
        
    except Exception as e:
        logger.error(f"Error archiving orders: {str(e)}")
        raise
    finally:
        db.close()
