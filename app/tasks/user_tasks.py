"""User-related Celery tasks"""

from celery.utils.log import get_task_logger
from datetime import datetime, timedelta
import asyncio

from app.core.celery_app import celery_app
from app.core.database import get_db_sync

logger = get_task_logger(__name__)

@celery_app.task(name="update_user_streaks")
def update_user_streaks():
    """Update user check-in streaks"""
    try:
        db = next(get_db_sync())
        
        # Reset streaks for users who missed check-in
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        
        query = """
        UPDATE users
        SET checkin_streak = 0
        WHERE last_checkin_date < :yesterday
        AND checkin_streak > 0
        """
        
        result = db.execute(query, {"yesterday": yesterday})
        reset_count = result.rowcount
        
        db.commit()
        
        logger.info(f"Reset {reset_count} user streaks")
        
        return {"reset_count": reset_count}
        
    except Exception as e:
        logger.error(f"Error updating user streaks: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="log_user_activity")
def log_user_activity(
    user_id: str,
    activity_type: str,
    metadata: Dict[str, Any] = None
):
    """Log user activity for analytics"""
    try:
        db = next(get_db_sync())
        
        from app.models.analytics import UserActivity
        
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            metadata=metadata or {},
            ip_address=metadata.get("ip_address") if metadata else None,
            user_agent=metadata.get("user_agent") if metadata else None
        )
        
        db.add(activity)
        db.commit()
        
        logger.info(f"Logged {activity_type} activity for user {user_id}")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error logging user activity: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="expire_old_coins")
def expire_old_coins():
    """Expire coins that have passed their expiry date"""
    try:
        db = next(get_db_sync())
        
        from app.services.coins import CoinService
        service = CoinService(db)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(service.expire_coins())
        loop.close()
        
        logger.info("Processed coin expiration")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error expiring coins: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="calculate_user_badges")
def calculate_user_badges(user_id: str):
    """Calculate and award badges based on user achievements"""
    try:
        db = next(get_db_sync())
        
        from app.services.badges import BadgeService
        service = BadgeService(db)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        badges_awarded = loop.run_until_complete(
            service.check_and_award_badges(user_id)
        )
        
        loop.close()
        
        logger.info(f"Awarded {len(badges_awarded)} badges to user {user_id}")
        
        return {
            "user_id": user_id,
            "badges_awarded": badges_awarded
        }
        
    except Exception as e:
        logger.error(f"Error calculating user badges: {str(e)}")
        raise
    finally:
        db.close()
