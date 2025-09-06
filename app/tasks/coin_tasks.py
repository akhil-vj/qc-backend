"""Coin-related background tasks"""

from app.core.celery_app import celery_app
from app.core.database import get_db_sync
from datetime import datetime, timedelta

@celery_app.task(name="expire_coins")
def expire_coins_task():
    """Expire coins that have passed expiry date"""
    try:
        db = next(get_db_sync())
        
        # Find and expire coins
        query = """
        UPDATE coin_transactions
        SET is_expired = TRUE
        WHERE expires_at < NOW()
        AND is_expired = FALSE
        RETURNING user_id, amount
        """
        
        result = db.execute(query)
        expired = result.fetchall()
        
        # Update user balances
        for user_id, amount in expired:
            db.execute(
                "UPDATE users SET coin_balance = coin_balance - %s WHERE id = %s",
                (amount, user_id)
            )
            
        db.commit()
        
        logger.info(f"Expired {len(expired)} coin transactions")
        
    except Exception as e:
        logger.error(f"Error expiring coins: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="award_streak_bonus")
def award_streak_bonus_task(user_id: str):
    """Award bonus coins for check-in streaks"""
    try:
        db = next(get_db_sync())
        
        from app.services.coins import CoinService
        service = CoinService(db)
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(
            service.award_streak_bonus(user_id)
        )
        
        loop.close()
        
    except Exception as e:
        logger.error(f"Error awarding streak bonus: {str(e)}")
        raise
    finally:
        db.close()
