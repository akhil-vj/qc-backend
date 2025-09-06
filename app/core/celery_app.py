"""Celery application configuration"""

from celery import Celery
from kombu import Exchange, Queue
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "quickcart",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.email_tasks",
        "app.tasks.sms_tasks",
        "app.tasks.analytics_tasks",
        "app.tasks.user_tasks",
        "app.tasks.cleanup_tasks"
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Task routing
    task_routes={
        "app.tasks.email_tasks.*": {"queue": "email"},
        "app.tasks.sms_tasks.*": {"queue": "sms"},
        "app.tasks.analytics_tasks.*": {"queue": "analytics"},
        "app.tasks.user_tasks.*": {"queue": "default"},
        "app.tasks.cleanup_tasks.*": {"queue": "cleanup"}
    },
    
    # Retry configuration
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Result backend configuration
    result_expires=3600,  # 1 hour
)

# Define queues
celery_app.conf.task_queues = (
    Queue("default", Exchange("default"), routing_key="default"),
    Queue("email", Exchange("email"), routing_key="email"),
    Queue("sms", Exchange("sms"), routing_key="sms"),
    Queue("analytics", Exchange("analytics"), routing_key="analytics"),
    Queue("cleanup", Exchange("cleanup"), routing_key="cleanup"),
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "update-user-streaks": {
        "task": "app.tasks.user_tasks.update_user_streaks",
        "schedule": 60 * 60,  # Every hour
    },
    "generate-analytics-snapshot": {
        "task": "app.tasks.analytics_tasks.generate_daily_analytics",
        "schedule": 60 * 60 * 24,  # Daily at midnight
        "options": {"queue": "analytics"}
    },
    "cleanup-expired-tokens": {
        "task": "app.tasks.cleanup_tasks.cleanup_expired_tokens",
        "schedule": 60 * 60 * 6,  # Every 6 hours
    },
    "expire-old-coins": {
        "task": "app.tasks.user_tasks.expire_old_coins",
        "schedule": 60 * 60 * 24,  # Daily
    },
    "send-abandoned-cart-reminders": {
        "task": "app.tasks.email_tasks.send_abandoned_cart_reminders",
        "schedule": 60 * 60 * 4,  # Every 4 hours
    },
}
