"""SMS-related Celery tasks"""

from celery import Task
from celery.utils.log import get_task_logger
from typing import List, Dict, Any
import asyncio

from app.core.celery_app import celery_app
from app.services.sms_service import SMSService

logger = get_task_logger(__name__)

class SMSTask(Task):
    """Base class for SMS tasks with retry logic"""
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 300  # 5 minutes

@celery_app.task(base=SMSTask, name="send_sms")
def send_sms_task(
    to_number: str,
    message: str,
    media_url: str = None
) -> bool:
    """Send SMS task"""
    try:
        logger.info(f"Sending SMS to {to_number}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        sms_service = SMSService()
        result = loop.run_until_complete(
            sms_service.send_sms(
                to_number=to_number,
                message=message,
                media_url=media_url
            )
        )
        
        loop.close()
        
        if result:
            logger.info(f"SMS sent successfully to {to_number}")
        else:
            logger.error(f"Failed to send SMS to {to_number}")
            
        return result
        
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        raise

@celery_app.task(name="send_bulk_sms")
def send_bulk_sms_task(
    sms_list: List[Dict[str, Any]],
    batch_size: int = 100
) -> Dict[str, int]:
    """Send bulk SMS with rate limiting"""
    sent_count = 0
    failed_count = 0
    
    for i in range(0, len(sms_list), batch_size):
        batch = sms_list[i:i + batch_size]
        
        for sms_data in batch:
            try:
                send_sms_task.apply_async(
                    args=[
                        sms_data["to_number"],
                        sms_data["message"]
                    ],
                    countdown=i * 0.5  # Rate limiting
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to queue SMS: {str(e)}")
                failed_count += 1
                
    return {
        "sent": sent_count,
        "failed": failed_count
    }
