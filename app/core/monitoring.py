# QuickCart Backend Monitoring Configuration
# Prometheus metrics, health checks, and logging setup

import logging
import logging.handlers
import os
import time
from datetime import datetime
from typing import Dict, Any
import psutil
import redis.asyncio as redis
from sqlalchemy import text
from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])
active_connections = Gauge('active_connections', 'Active database connections')
memory_usage = Gauge('memory_usage_bytes', 'Memory usage in bytes')
cpu_usage = Gauge('cpu_usage_percent', 'CPU usage percentage')

# Database metrics
db_query_count = Counter('database_queries_total', 'Total database queries', ['operation'])
db_query_duration = Histogram('database_query_duration_seconds', 'Database query duration', ['operation'])

# Redis metrics
redis_operations = Counter('redis_operations_total', 'Total Redis operations', ['operation'])
redis_connection_errors = Counter('redis_connection_errors_total', 'Redis connection errors')

def setup_logging():
    """Configure structured logging for the application"""
    
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE", "logs/quickcart.log")
    
    # Ensure logs directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=int(os.getenv("LOG_MAX_SIZE", "10MB").replace("MB", "")) * 1024 * 1024,
        backupCount=int(os.getenv("LOG_BACKUP_COUNT", "5"))
    )
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=[console_handler, file_handler]
    )
    
    # Silence noisy loggers in production
    if os.getenv("ENVIRONMENT") == "production":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

def setup_monitoring_middleware(app: FastAPI):
    """Add monitoring middleware to track metrics"""
    
    @app.middleware("http")
    async def monitor_requests(request: Request, call_next):
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate metrics
        process_time = time.time() - start_time
        
        # Update metrics
        request_count.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        request_duration.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(process_time)
        
        # Add response headers
        response.headers["X-Process-Time"] = str(process_time)
        
        return response

async def collect_system_metrics():
    """Collect system-level metrics"""
    
    # Memory usage
    memory = psutil.virtual_memory()
    memory_usage.set(memory.used)
    
    # CPU usage
    cpu = psutil.cpu_percent(interval=1)
    cpu_usage.set(cpu)

async def get_health_status(db_session, redis_client) -> Dict[str, Any]:
    """Get comprehensive health status of all services"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Database health
    try:
        result = await db_session.execute(text("SELECT 1"))
        health_status["services"]["database"] = {
            "status": "healthy",
            "response_time_ms": 0  # Could add timing here
        }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
    
    # Redis health
    try:
        await redis_client.ping()
        health_status["services"]["redis"] = {
            "status": "healthy"
        }
    except Exception as e:
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
    
    # System resources
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    health_status["system"] = {
        "memory_usage_percent": memory.percent,
        "disk_usage_percent": disk.percent,
        "cpu_usage_percent": psutil.cpu_percent()
    }
    
    return health_status

def setup_health_endpoints(app: FastAPI):
    """Setup health check endpoints"""
    
    @app.get("/health")
    async def health_check():
        """Basic health check endpoint"""
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    
    @app.get("/health/detailed")
    async def detailed_health_check():
        """Detailed health check with all services"""
        # This would need database and redis dependencies injected
        return {"status": "healthy", "message": "Detailed health check endpoint"}
    
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint"""
        if not os.getenv("PROMETHEUS_ENABLED", "True").lower() == "true":
            return {"error": "Metrics disabled"}
        
        # Collect current system metrics
        await collect_system_metrics()
        
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Logging utilities
logger = logging.getLogger(__name__)

def log_database_operation(operation: str, duration: float, success: bool = True):
    """Log database operations with metrics"""
    db_query_count.labels(operation=operation).inc()
    db_query_duration.labels(operation=operation).observe(duration)
    
    if success:
        logger.info(f"Database {operation} completed in {duration:.3f}s")
    else:
        logger.error(f"Database {operation} failed after {duration:.3f}s")

def log_redis_operation(operation: str, success: bool = True):
    """Log Redis operations with metrics"""
    redis_operations.labels(operation=operation).inc()
    
    if not success:
        redis_connection_errors.inc()
        logger.error(f"Redis {operation} failed")

# Context managers for operation logging
class DatabaseOperationContext:
    def __init__(self, operation: str):
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        success = exc_type is None
        log_database_operation(self.operation, duration, success)

class RedisOperationContext:
    def __init__(self, operation: str):
        self.operation = operation
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        log_redis_operation(self.operation, success)
