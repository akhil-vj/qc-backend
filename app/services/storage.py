"""
File storage service using Cloudinary
"""

import cloudinary
import cloudinary.uploader
from typing import Optional, Dict, Any, List
import asyncio
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

class StorageService:
    """Storage service for file uploads"""
    
    def __init__(self):
        # Configure Cloudinary
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET
        )
    
    async def upload_image(
        self,
        file_path: str,
        folder: str = "products",
        public_id: Optional[str] = None,
        transformation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Upload image to Cloudinary
        
        Args:
            file_path: Local file path
            folder: Cloudinary folder
            public_id: Custom public ID
            transformation: Image transformations
            
        Returns:
            Upload result with URL
        """
        try:
            # Run in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._upload_image_sync,
                file_path,
                folder,
                public_id,
                transformation
            )
            return result
        except Exception as e:
            logger.error(f"Failed to upload image: {str(e)}")
            raise
    
    def _upload_image_sync(
        self,
        file_path: str,
        folder: str,
        public_id: Optional[str],
        transformation: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Upload image synchronously"""
        options = {
            "folder": folder,
            "resource_type": "image",
            "allowed_formats": ["jpg", "jpeg", "png", "webp"],
            "max_file_size": settings.MAX_UPLOAD_SIZE
        }
        
        if public_id:
            options["public_id"] = public_id
        
        if transformation:
            options["transformation"] = transformation
        
        result = cloudinary.uploader.upload(file_path, **options)
        
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "width": result.get("width"),
            "height": result.get("height"),
            "format": result.get("format"),
            "size": result.get("bytes")
        }
    
    async def upload_multiple_images(
        self,
        file_paths: List[str],
        folder: str = "products"
    ) -> List[Dict[str, Any]]:
        """Upload multiple images"""
        tasks = [
            self.upload_image(file_path, folder)
            for file_path in file_paths
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors
        return [r for r in results if not isinstance(r, Exception)]
    
    async def delete_image(self, public_id: str) -> bool:
        """Delete image from Cloudinary"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                cloudinary.uploader.destroy,
                public_id
            )
            return result.get("result") == "ok"
        except Exception as e:
            logger.error(f"Failed to delete image: {str(e)}")
            return False
    
    def get_optimized_url(
        self,
        public_id: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        crop: str = "fill",
        quality: str = "auto",
        format: str = "auto"
    ) -> str:
        """Get optimized image URL"""
        transformations = {
            "quality": quality,
            "fetch_format": format,
            "crop": crop
        }
        
        if width:
            transformations["width"] = width
        if height:
            transformations["height"] = height
        
        return cloudinary.CloudinaryImage(public_id).build_url(**transformations)
