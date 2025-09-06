"""AI-related background tasks"""

from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.core.database import get_db_sync
from app.services.ai_categorization import AICategorizationService

logger = get_task_logger(__name__)

@celery_app.task(name="categorize_product")
def categorize_product_task(product_id: str, title: str, description: str):
    """Background task to categorize product using AI"""
    try:
        db = next(get_db_sync())
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        service = AICategorizationService(db)
        category_id = loop.run_until_complete(
            service.auto_categorize_product(product_id, title, description)
        )
        
        loop.close()
        
        if category_id:
            logger.info(f"Successfully categorized product {product_id}")
        else:
            logger.info(f"Could not auto-categorize product {product_id}")
            
        return {"success": True, "category_id": category_id}
        
    except Exception as e:
        logger.error(f"Error categorizing product: {str(e)}")
        raise
    finally:
        db.close()
