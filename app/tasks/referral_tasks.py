"""Referral-related background tasks"""

from app.core.celery_app import celery_app
from app.core.database import get_db_sync

@celery_app.task(name="process_referral_reward")
def process_referral_reward(order_id: str, referral_code: str):
    """Process referral rewards after order confirmation"""
    try:
        db = next(get_db_sync())
        
        from app.services.referral import ReferralService
        service = ReferralService(db)
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(
            service.process_order_referral(order_id, referral_code)
        )
        
        loop.close()
        
    except Exception as e:
        logger.error(f"Error processing referral reward: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="update_referral_stats")
def update_referral_stats():
    """Update referral statistics"""
    try:
        db = next(get_db_sync())
        
        # Update referral counts and rankings
        query = """
        UPDATE users u
        SET referral_stats = subquery.stats
        FROM (
            SELECT 
                referrer_id,
                jsonb_build_object(
                    'total_referrals', COUNT(*),
                    'successful_referrals', COUNT(*) FILTER (WHERE status = 'completed'),
                    'total_earnings', SUM(referrer_reward)
                ) as stats
            FROM referral_tracking
            GROUP BY referrer_id
        ) subquery
        WHERE u.id = subquery.referrer_id
        """
        
        db.execute(query)
        db.commit()
        
    except Exception as e:
        logger.error(f"Error updating referral stats: {str(e)}")
        raise
    finally:
        db.close()
