"""Complete product service with all database operations"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from datetime import datetime
import uuid
import csv
import io
import pandas as pd

from app.models.product import Product, ProductVariant, ProductImage
from app.models.category import Category
from app.models.review import Review

class ProductService:
    """Complete product service with business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def create_product(
        self,
        seller_id: str,
        product_data: Dict[str, Any]
    ) -> Product:
        """Create new product with validation"""
        # Validate category
        if product_data.get("category_id"):
            category = await self.db.get(Category, product_data["category_id"])
            if not category:
                raise ValueError("Invalid category")
                
        # Create product
        product = Product(
            **product_data,
            seller_id=seller_id,
            status="pending"  # Pending admin approval
        )
        
        # Generate SKU if not provided
        if not product.sku:
            product.sku = await self._generate_sku(product)
            
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        
        return product
        
    async def bulk_upload_products(
        self,
        seller_id: str,
        file_content: bytes,
        file_type: str
    ) -> Dict[str, Any]:
        """Bulk upload products from CSV/Excel"""
        try:
            # Parse file
            if file_type == 'csv':
                df = pd.read_csv(io.BytesIO(file_content))
            else:
                df = pd.read_excel(io.BytesIO(file_content))
                
            # Validate columns
            required_columns = ['title', 'description', 'category', 'price', 'stock']
            missing_columns = set(required_columns) - set(df.columns)
            
            if missing_columns:
                return {
                    "success": False,
                    "error": f"Missing required columns: {', '.join(missing_columns)}",
                    "products_created": 0
                }
                
            # Get category mapping
            categories = await self.db.execute(select(Category))
            category_map = {c.name.lower(): c.id for c in categories.scalars()}
            
            created_products = []
            errors = []
            
            for idx, row in df.iterrows():
                try:
                    # Map category
                    category_name = str(row['category']).lower()
                    category_id = category_map.get(category_name)
                    
                    if not category_id:
                        errors.append(f"Row {idx + 2}: Invalid category '{row['category']}'")
                        continue
                        
                    # Create product
                    product_data = {
                        "title": row['title'],
                        "description": row['description'],
                        "category_id": category_id,
                        "price": float(row['price']),
                        "mrp": float(row.get('mrp', row['price'])),
                        "stock": int(row['stock']),
                        "brand": row.get('brand'),
                        "tags": row.get('tags', '').split(',') if pd.notna(row.get('tags')) else [],
                        "seller_id": seller_id,
                        "status": "pending"
                    }
                    
                    product = Product(**product_data)
                    product.sku = await self._generate_sku(product)
                    
                    self.db.add(product)
                    created_products.append(product)
                    
                except Exception as e:
                    errors.append(f"Row {idx + 2}: {str(e)}")
                    
            await self.db.commit()
            
            return {
                "success": True,
                "products_created": len(created_products),
                "errors": errors,
                "created_product_ids": [str(p.id) for p in created_products]
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "products_created": 0
            }
            
    async def update_product_images(
        self,
        product_id: str,
        image_urls: List[str]
    ):
        """Update product images"""
        # Get existing images
        existing = await self.db.execute(
            select(ProductImage).where(ProductImage.product_id == product_id)
        )
        existing_images = existing.scalars().all()
        
        # Add new images
        for idx, url in enumerate(image_urls):
            image = ProductImage(
                product_id=product_id,
                image_url=url,
                is_primary=(idx == 0 and not existing_images),
                display_order=len(existing_images) + idx
            )
            self.db.add(image)
            
        # Update product primary image if first image
        if image_urls and not existing_images:
            product = await self.db.get(Product, product_id)
            product.primary_image = image_urls[0]
            
        await self.db.commit()
        
    async def get_review_summary(self, product_id: str) -> Dict[str, Any]:
        """Get aggregated review summary"""
        # Get rating distribution
        rating_dist = await self.db.execute(
            text("""
            SELECT 
                rating,
                COUNT(*) as count,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
            FROM reviews
            WHERE product_id = :product_id
            GROUP BY rating
            ORDER BY rating DESC
            """),
            {"product_id": product_id}
        )
        
        # Get review stats
        stats = await self.db.execute(
            text("""
            SELECT 
                COUNT(*) as total_reviews,
                AVG(rating) as avg_rating,
                COUNT(DISTINCT user_id) as unique_reviewers,
                COUNT(CASE WHEN has_images = TRUE THEN 1 END) as reviews_with_images
            FROM reviews
            WHERE product_id = :product_id
            """),
            {"product_id": product_id}
        )
        
        stats_data = stats.fetchone()._asdict()
        
        # Get recent reviews
        recent = await self.db.execute(
            select(Review)
            .where(Review.product_id == product_id)
            .order_by(Review.created_at.desc())
            .limit(5)
        )
        
        return {
            "summary": {
                "total_reviews": stats_data["total_reviews"],
                "average_rating": float(stats_data["avg_rating"]) if stats_data["avg_rating"] else 0,
                "unique_reviewers": stats_data["unique_reviewers"],
                "reviews_with_images": stats_data["reviews_with_images"]
            },
            "rating_distribution": [
                {
                    "rating": row.rating,
                    "count": row.count,
                    "percentage": float(row.percentage)
                }
                for row in rating_dist
            ],
            "recent_reviews": [
                {
                    "id": str(r.id),
                    "rating": r.rating,
                    "comment": r.comment,
                    "user_name": r.user.name,
                    "created_at": r.created_at.isoformat(),
                    "verified_purchase": r.verified_purchase
                }
                for r in recent.scalars()
            ]
        }
        
    async def search_products(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "relevance",
        page: int = 1,
        size: int = 20
    ) -> Dict[str, Any]:
        """Advanced product search with filtering"""
        # Build base query
        stmt = select(Product).where(Product.status == "active")
        
        # Apply search query
        if query:
            search_terms = query.split()
            search_conditions = []
            
            for term in search_terms:
                term_pattern = f"%{term}%"
                search_conditions.append(
                    or_(
                        Product.title.ilike(term_pattern),
                        Product.description.ilike(term_pattern),
                        Product.brand.ilike(term_pattern),
                        Product.tags.contains([term])
                    )
                )
                
            stmt = stmt.where(and_(*search_conditions))
            
        # Apply filters
        if filters:
            if filters.get("category_id"):
                stmt = stmt.where(Product.category_id == filters["category_id"])
                
            if filters.get("min_price"):
                stmt = stmt.where(Product.price >= filters["min_price"])
                
            if filters.get("max_price"):
                stmt = stmt.where(Product.price <= filters["max_price"])
                
            if filters.get("brands"):
                stmt = stmt.where(Product.brand.in_(filters["brands"]))
                
            if filters.get("min_rating"):
                stmt = stmt.where(Product.rating >= filters["min_rating"])
                
            if filters.get("in_stock"):
                stmt = stmt.where(Product.stock > 0)
                
            if filters.get("tags"):
                stmt = stmt.where(Product.tags.overlap(filters["tags"]))
                
        # Apply sorting
        sort_options = {
            "relevance": Product.trending_score.desc(),
            "price_low": Product.price.asc(),
            "price_high": Product.price.desc(),
            "rating": Product.rating.desc(),
            "newest": Product.created_at.desc(),
            "popularity": Product.purchase_count.desc()
        }
        
        sort_column = sort_options.get(sort_by, Product.trending_score.desc())
        stmt = stmt.order_by(sort_column)
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt)
        
        # Apply pagination
        stmt = stmt.offset((page - 1) * size).limit(size)
        
        # Execute query
        result = await self.db.execute(stmt)
        products = result.scalars().all()
        
        return {
            "products": [p.to_dict() for p in products],
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size
        }
        
    async def _generate_sku(self, product: Product) -> str:
        """Generate unique SKU for product"""
        # Format: BRAND-CAT-XXXXX
        brand_prefix = (product.brand[:3] if product.brand else "GEN").upper()
        
        # Get category code
        category = await self.db.get(Category, product.category_id)
        cat_prefix = category.name[:3].upper() if category else "UNC"
        
        # Generate unique number
        count = await self.db.scalar(
            select(func.count(Product.id)).where(
                Product.sku.like(f"{brand_prefix}-{cat_prefix}-%")
            )
        )
        
        return f"{brand_prefix}-{cat_prefix}-{count + 1:05d}"
