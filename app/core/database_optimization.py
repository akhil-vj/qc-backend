"""Database optimization utilities"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    """Database optimization utilities"""
    
    @staticmethod
    async def analyze_slow_queries(db: AsyncSession):
        """Analyze slow queries using pg_stat_statements"""
        query = """
        SELECT 
            query,
            calls,
            total_time,
            mean_time,
            min_time,
            max_time
        FROM pg_stat_statements
        WHERE mean_time > 100  -- Queries taking more than 100ms
        ORDER BY mean_time DESC
        LIMIT 20
        """
        
        try:
            result = await db.execute(text(query))
            slow_queries = result.fetchall()
            
            for query_info in slow_queries:
                logger.warning(
                    f"Slow query detected: {query_info.query[:100]}... "
                    f"Mean time: {query_info.mean_time}ms, Calls: {query_info.calls}"
                )
                
            return slow_queries
            
        except Exception as e:
            logger.error(f"Error analyzing slow queries: {str(e)}")
            return []
            
    @staticmethod
    async def update_table_statistics(db: AsyncSession):
        """Update table statistics for query planner"""
        tables = [
            "users", "products", "orders", "order_items",
            "cart_items", "notifications", "coin_transactions"
        ]
        
        for table in tables:
            try:
                await db.execute(text(f"ANALYZE {table}"))
                logger.info(f"Updated statistics for table: {table}")
            except Exception as e:
                logger.error(f"Error updating statistics for {table}: {str(e)}")
                
    @staticmethod
    async def vacuum_tables(db: AsyncSession):
        """Vacuum tables to reclaim space"""
        tables = ["orders", "order_items", "notifications", "analytics_events"]
        
        for table in tables:
            try:
                # Note: VACUUM cannot run inside a transaction block
                await db.execute(text(f"VACUUM ANALYZE {table}"))
                logger.info(f"Vacuumed table: {table}")
            except Exception as e:
                logger.error(f"Error vacuuming {table}: {str(e)}")
                
    @staticmethod
    async def create_materialized_views(db: AsyncSession):
        """Create materialized views for complex queries"""
        views = [
            {
                "name": "mv_product_analytics",
                "query": """
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_product_analytics AS
                SELECT 
                    p.id,
                    p.title,
                    p.seller_id,
                    COUNT(DISTINCT oi.order_id) as order_count,
                    SUM(oi.quantity) as total_sold,
                    AVG(r.rating) as avg_rating,
                    COUNT(DISTINCT r.id) as review_count
                FROM products p
                LEFT JOIN order_items oi ON p.id = oi.product_id
                LEFT JOIN reviews r ON p.id = r.product_id
                GROUP BY p.id, p.title, p.seller_id
                """
            },
            {
                "name": "mv_user_statistics",
                "query": """
                CREATE MATERIALIZED VIEW IF NOT EXISTS mv_user_statistics AS
                SELECT 
                    u.id,
                    COUNT(DISTINCT o.id) as order_count,
                    SUM(o.total_amount) as lifetime_value,
                    COUNT(DISTINCT rt.referred_user_id) as referral_count,
                    u.coin_balance
                FROM users u
                LEFT JOIN orders o ON u.id = o.buyer_id
                LEFT JOIN referral_tracking rt ON u.id = rt.referrer_id
                GROUP BY u.id, u.coin_balance
                """
            }
        ]
        
        for view in views:
            try:
                await db.execute(text(view["query"]))
                await db.execute(
                    text(f"CREATE UNIQUE INDEX idx_{view['name']}_id ON {view['name']}(id)")
                )
                logger.info(f"Created materialized view: {view['name']}")
            except Exception as e:
                logger.error(f"Error creating view {view['name']}: {str(e)}")
                
    @staticmethod
    async def refresh_materialized_views(db: AsyncSession):
        """Refresh materialized views"""
        views = ["mv_product_analytics", "mv_user_statistics"]
        
        for view in views:
            try:
                await db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
                logger.info(f"Refreshed materialized view: {view}")
            except Exception as e:
                logger.error(f"Error refreshing view {view}: {str(e)}")
