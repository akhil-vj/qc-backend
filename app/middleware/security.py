"""Security middleware and utilities"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import bleach
import re
import os
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for input sanitization and headers"""
    
    async def dispatch(self, request: Request, call_next):
        # Add security headers
        response = await call_next(request)
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Check if this is a documentation endpoint
        path = request.url.path
        is_docs_endpoint = path.startswith('/api/docs') or path.startswith('/api/redoc') or path.startswith('/openapi.json')
        
        if is_docs_endpoint:
            # More permissive CSP for documentation
            response.headers["Content-Security-Policy"] = (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval' https: data: blob:; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https: blob:; "
                "style-src 'self' 'unsafe-inline' https:; "
                "font-src 'self' https: data:; "
                "img-src 'self' data: https: blob:; "
                "connect-src 'self' https: wss:; "
                "worker-src 'self' blob: data:; "
                "child-src 'self' blob: data:"
            )
        else:
            # Strict CSP for other endpoints
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net blob:; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
                "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "connect-src 'self' wss: https:; "
                "worker-src 'self' blob:; "
                "child-src 'self' blob:"
            )
        
        return response

def sanitize_input(data: Any) -> Any:
    """Recursively sanitize input data"""
    if isinstance(data, str):
        # Remove null bytes
        data = data.replace("\x00", "")
        
        # Basic HTML sanitization
        data = bleach.clean(
            data,
            tags=['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li'],
            attributes={'a': ['href', 'title']},
            strip=True
        )
        
        # Remove script tags and javascript
        data = re.sub(r'<script[^>]*>.*?</script>', '', data, flags=re.DOTALL | re.IGNORECASE)
        data = re.sub(r'javascript:', '', data, flags=re.IGNORECASE)
        data = re.sub(r'on\w+\s*=', '', data, flags=re.IGNORECASE)
        
        return data
        
    elif isinstance(data, dict):
        return {key: sanitize_input(value) for key, value in data.items()}
        
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
        
    return data

def validate_file_upload(filename: str, content_type: str, max_size: int = 10 * 1024 * 1024):
    """Validate file uploads"""
    # Check file extension
    allowed_extensions = {
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/gif': ['.gif'],
        'image/webp': ['.webp'],
        'application/pdf': ['.pdf']
    }
    
    if content_type not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type {content_type} not allowed"
        )
        
    # Check filename
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions[content_type]:
        raise HTTPException(
            status_code=400,
            detail=f"File extension {ext} does not match content type"
        )
        
    # Sanitize filename
    filename = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
    
    return filename

class InputSanitizer:
    """Input sanitization for specific fields"""
    
    @staticmethod
    def sanitize_product_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize product input data"""
        if 'title' in data:
            data['title'] = bleach.clean(data['title'], tags=[], strip=True)
            data['title'] = data['title'][:200]  # Limit length
            
        if 'description' in data:
            # Allow some HTML in description
            data['description'] = bleach.clean(
                data['description'],
                tags=['p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li'],
                strip=True
            )
            data['description'] = data['description'][:5000]
            
        return data
        
    @staticmethod
    def sanitize_message(message: str) -> str:
        """Sanitize chat messages"""
        # Remove all HTML
        message = bleach.clean(message, tags=[], strip=True)
        
        # Limit length
        message = message[:1000]
        
        # Remove excessive whitespace
        message = ' '.join(message.split())
        
        return message
        
    @staticmethod
    def sanitize_review(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize review data"""
        if 'comment' in data:
            # Remove all HTML
            data['comment'] = bleach.clean(data['comment'], tags=[], strip=True)
            data['comment'] = data['comment'][:1000]
            
        if 'rating' in data:
            # Ensure rating is between 1-5
            data['rating'] = max(1, min(5, int(data['rating'])))
            
        return data
