"""Main FastAPI application with all middleware"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import engine
from app.middleware.rate_limit import limiter, custom_rate_limit_handler
from app.middleware.security import SecurityMiddleware
from app.core.websocket import router as websocket_router
from app.api.v1.websocket_routes import router as websocket_routes_router
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting up QuickCart API...")
    
    # Initialize database
    async with engine.begin() as conn:
        # Run any startup SQL if needed
        pass
        
    # Initialize services
    from app.core.celery_app import celery_app
    logger.info("Celery app initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down QuickCart API...")

# Create FastAPI app
app = FastAPI(
    title="QuickCart API",
    description="Community-driven shopping platform API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SecurityMiddleware)

# Include routers
from app.api.v1 import api_router
app.include_router(api_router, prefix="/api/v1")
app.include_router(websocket_router)
app.include_router(websocket_routes_router, prefix="/api/v1")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to QuickCart API",
        "docs": "/api/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=settings.WORKERS
    )



# """
# Main FastAPI application
# """

# from fastapi import FastAPI, Request
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# import time

# from app.core.config import settings
# from app.core.events import lifespan
# from app.core.middleware import setup_middleware
# from app.api import api_router

# # Create FastAPI app
# app = FastAPI(
#     title=settings.APP_NAME,
#     version=settings.APP_VERSION,
#     description="QuickCart API - Community-driven shopping platform",
#     docs_url="/api/docs",
#     redoc_url="/api/redoc",
#     openapi_url="/api/openapi.json",
#     lifespan=lifespan
# )

# # Setup middleware
# setup_middleware(app)

# # Include API routes
# app.include_router(api_router, prefix="/api")

# # Root endpoint
# @app.get("/")
# async def root():
#     """Root endpoint"""
#     return {
#         "app": settings.APP_NAME,
#         "version": settings.APP_VERSION,
#         "status": "running",
#         "docs": "/api/docs"
#     }

# # Health check
# @app.get("/health")
# async def health_check():
#     """Health check endpoint"""
#     return {
#         "status": "healthy",
#         "timestamp": time.time()
#     }

# # Custom 404 handler
# @app.exception_handler(404)
# async def not_found_handler(request: Request, exc):
#     """Custom 404 handler"""
#     return JSONResponse(
#         status_code=404,
#         content={
#             "error": {
#                 "code": "NOT_FOUND",
#                 "message": f"Path {request.url.path} not found"
#             }
#         }
#     )

# # Custom 500 handler
# @app.exception_handler(500)
# async def internal_error_handler(request: Request, exc):
#     """Custom 500 handler"""
#     return JSONResponse(
#         status_code=500,
#         content={
#             "error": {
#                 "code": "INTERNAL_ERROR",
#                 "message": "An internal error occurred"
#             }
#         }
#     )

# if __name__ == "__main__":
#     import uvicorn
    
#     uvicorn.run(
#         "app.main:app",
#         host=settings.HOST,
#         port=settings.PORT,
#         reload=settings.DEBUG,
#         workers=1 if settings.DEBUG else settings.WORKERS
#     )
