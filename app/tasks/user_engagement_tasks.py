"""User engagement and retention tasks"""

from celery.utils.log import get_task_logger
from datetime import datetime, timedelta
import asyncio

from app.core.celery_app import celery_app
from app.core.database import get_db_sync

logger = get_task_logger(__name__)

@celery_app.task(name="send_personalized_recommendations")
def send_personalized_recommendations():
    """Send personalized product recommendations to users"""
    try:
        db = next(get_db_sync())
        
        # Get active users who haven't received recommendations recently
        from app.models.user import User
        
        eligible_users = db.query(User).filter(
            User.role == 'buyer',
            User.is_active == True,
            or_(
                User.last_recommendation_sent_at.is_(None),
                User.last_recommendation_sent_at < datetime.utcnow() - timedelta(days=7)
            )
        ).limit(1000).all()  # Process in batches
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from app.services.recommendation import RecommendationService
        from app.tasks.push_notification_tasks import send_push_notification_task
        
        sent_count = 0
        
        for user in eligible_users:
            try:
                # Get recommendations
                rec_service = RecommendationService(db)
                recommendations = loop.run_until_complete(
                    rec_service.get_personalized_recommendations(
                        user_id=str(user.id),
                        limit=5
                    )
                )
                
                if recommendations:
                    # Send push notification
                    send_push_notification_task.delay(
                        user_id=str(user.id),
                        title="Handpicked for You! 🎯",
                        body=f"Check out {recommendations[0]['title']} and more items we think you'll love",
                        data={
                            "type": "recommendations",
                            "product_ids": [r['id'] for r in recommendations[:3]]
                        }
                    )
                    
                    # Update last sent time
                    user.last_recommendation_sent_at = datetime.utcnow()
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Error sending recommendations to user {user.id}: {str(e)}")
                continue
                
        db.commit()
        loop.close()
        
        logger.info(f"Sent personalized recommendations to {sent_count} users")
        
        return {"users_notified": sent_count}
        
    except Exception as e:
        logger.error(f"Error sending personalized recommendations: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="reward_user_milestones")
def reward_user_milestones():
    """Check and reward user milestones"""
    try:
        db = next(get_db_sync())
        
        # Define milestones
        milestones = [
            {"orders": 1, "coins": 100, "badge": "first_purchase", "title": "First Purchase!"},
            {"orders": 5, "coins": 200, "badge": "regular_shopper", "title": "Regular Shopper!"},
            {"orders": 10, "coins": 500, "badge": "loyal_customer", "title": "Loyal Customer!"},
            {"orders": 25, "coins": 1000, "badge": "vip_member", "title": "VIP Member!"},
            {"orders": 50, "coins": 2500, "badge": "elite_shopper", "title": "Elite Shopper!"}
        ]
        
        # Check users for milestones
        query = """
        WITH user_stats AS (
            SELECT 
                u.id,
                u.name,
                COUNT(DISTINCT o.id) as total_orders,
                COALESCE(u.milestones_achieved, '[]'::jsonb) as achieved_milestones
            FROM users u
            LEFT JOIN orders o ON u.id = o.buyer_id
                AND o.status IN ('delivered')
            WHERE u.role = 'buyer'
            GROUP BY u.id, u.name, u.milestones_achieved
        )
        SELECT * FROM user_stats
        WHERE total_orders > 0
        """
        
        users = db.execute(query).fetchall()
        
        from app.models.coin_transaction import CoinTransaction
        from app.models.user_badge import UserBadge
        from app.tasks.push_notification_tasks import send_push_notification_task
        
        rewards_given = 0
        
        for user in users:
            achieved = set(user.achieved_milestones or [])
            
            for milestone in milestones:
                milestone_key = f"orders_{milestone['orders']}"
                
                if user.total_orders >= milestone['orders'] and milestone_key not in achieved:
                    # Award coins
                    db_user = db.query(User).filter(User.id == user.id).first()
                    db_user.coin_balance += milestone['coins']
                    
                    # Create coin transaction
                    transaction = CoinTransaction(
                        user_id=user.id,
                        amount=milestone['coins'],
                        transaction_type='earned',
                        source='milestone_reward',
                        description=f"Milestone: {milestone['title']}",
                        balance_after=db_user.coin_balance
                    )
                    db.add(transaction)
                    
                    # Award badge
                    badge = UserBadge(
                        user_id=user.id,
                        badge_code=milestone['badge'],
                        awarded_at=datetime.utcnow()
                    )
                    db.add(badge)
                    
                    # Update achieved milestones
                    achieved.add(milestone_key)
                    db_user.milestones_achieved = list(achieved)
                    
                    # Send notification
                    send_push_notification_task.delay(
                        user_id=str(user.id),
                        title=f"🎉 {milestone['title']}",
                        body=f"Congratulations! You've earned {milestone['coins']} coins and a new badge!",
                        data={
                            "type": "milestone",
                            "milestone": milestone_key,
                            "coins": milestone['coins']
                        },
                        priority="high"
                    )
                    
                    rewards_given += 1
                    
        db.commit()
        
        logger.info(f"Rewarded {rewards_given} user milestones")
        
        return {"rewards_given": rewards_given}
        
    except Exception as e:
        logger.error(f"Error rewarding user milestones: {str(e)}")
        raise
    finally:
        db.close()

@celery_app.task(name="cleanup_expired_sessions")
def cleanup_expired_sessions():
    """Clean up expired user sessions and temporary data"""
    try:
        db = next(get_db_sync())
        
        # Clean expired sessions
        sessions_deleted = db.execute("""
            DELETE FROM user_sessions
            WHERE expires_at < NOW()
        """).rowcount
        
        # Clean abandoned session carts (>30 days)
        carts_deleted = db.execute("""
            DELETE FROM cart_items
            WHERE user_id IS NULL
            AND created_at < NOW() - INTERVAL '30 days'
        """).rowcount
        
        # Clean old analytics events (>90 days)
        events_deleted = db.execute("""
            DELETE FROM user_activities
            WHERE created_at < NOW() - INTERVAL '90 days'
        """).rowcount
        
        # Clean old notifications (read and >30 days)
        notifications_deleted = db.execute("""
            DELETE FROM notifications
            WHERE is_read = TRUE
            AND created_at < NOW() - INTERVAL '30 days'
        """).rowcount
        
        db.commit()
        
        logger.info(
            f"Cleanup complete - Sessions: {sessions_deleted}, "
            f"Carts: {carts_deleted}, Events: {events_deleted}, "
            f"Notifications: {notifications_deleted}"
        )
        
        return {
            "sessions_deleted": sessions_deleted,
            "carts_deleted": carts_deleted,
            "events_deleted": events_deleted,
            "notifications_deleted": notifications_deleted
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise
    finally:
        db.close()
