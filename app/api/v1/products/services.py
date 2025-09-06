"""
Product service layer
Handles business logic for products
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
import uuid
import slugify

from app.models import Product, ProductVariant, Category, Brand, User, Review
from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException
from app.core.cache import cache, cached, invalidate_cache
from app.services.storage import StorageService
from app.services.ai_categorization import AICategorization
from .schemas import ProductCreate, ProductUpdate, ProductSearchRequest
from .filters import ProductFilter

class ProductService:
    """Product service for business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = StorageService()
        self.ai_categorizer = AICategorization()
    
    async def create_product(
        self,
        seller_id: uuid.UUID,
        data: ProductCreate
    ) -> Product:
        """
        Create new product
        
        Args:
            seller_id: Seller user ID
            data: Product creation data
            
        Returns:
            Created product
        """
        # Generate slug
        slug = slugify.slugify(data.title)
        
        # Check slug uniqueness
        existing = await self.db.execute(
            select(Product).where(Product.slug == slug)
        )
        if existing.scalar_one_or_none():
            # Add random suffix for uniqueness
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        
        # Create product
        product_data = data.dict(exclude={'variants', 'images'})
        product = Product(
            seller_id=seller_id,
            slug=slug,
            **product_data
        )
        
        # Calculate discount percentage if MRP provided
        if product.mrp and product.mrp > product.price:
            product.discount_percentage = ((product.mrp - product.price) / product.mrp) * 100
        
        # AI category suggestion
        if not product.category_id:
            suggestion = await self.ai_categorizer.suggest_category(
                title=data.title,
                description=data.description
            )
            product.ai_category_suggestion = suggestion
        
        # Add variants if provided
        for variant_data in data.variants:
            variant = ProductVariant(
                product_id=product.id,
                **variant_data.dict()
            )
            self.db.add(variant)
        
        # Set published_at if status is active
        if product.status == "active":
            product.published_at = datetime.utcnow()
        
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        
        # Invalidate cache
        await cache.delete_pattern("products:*")
        
        return product
    
    async def update_product(
        self,
        product_id: uuid.UUID,
        seller_id: uuid.UUID,
        data: ProductUpdate
    ) -> Product:
        """
        Update existing product
        
        Args:
            product_id: Product ID
            seller_id: Seller user ID
            data: Update data
            
        Returns:
            Updated product
            
        Raises:
            NotFoundException: If product not found
            ForbiddenException: If not the seller
        """
        # Get product
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        
        if not product:
            raise NotFoundException("Product not found")
        
        if product.seller_id != seller_id:
            raise ForbiddenException("You can only update your own products")
        
        # Update fields
        update_data = data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(product, field, value)
        
        # Recalculate discount
        if product.mrp and product.price:
            if product.mrp > product.price:
                product.discount_percentage = ((product.mrp - product.price) / product.mrp) * 100
            else:
                product.discount_percentage = 0
        
        # Update published_at
        if data.status == "active" and not product.published_at:
            product.published_at = datetime.utcnow()
        
        product.updated_at = datetime.utcnow()
        
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        
        # Invalidate cache
        await cache.delete_pattern(f"products:{product_id}:*")
        await cache.delete_pattern("products:list:*")
        
        return product
    
    @cached(key_prefix="products:detail", expire=3600)
    async def get_product(
        self,
        product_id: uuid.UUID,
        increment_view: bool = True
    ) -> Product:
        """
        Get product details
        
        Args:
            product_id: Product ID
            increment_view: Whether to increment view count
            
        Returns:
            Product with related data
            
        Raises:
            NotFoundException: If product not found or inactive
        """
        # Get product with related data
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.seller),
                selectinload(Product.category),
                selectinload(Product.brand),
                selectinload(Product.variants),
                selectinload(Product.reviews)
            )
            .where(
                and_(
                    Product.id == product_id,
                    Product.status.in_(["active", "out_of_stock"])
                )
            )
        )
        product = result.scalar_one_or_none()
        
        if not product:
            raise NotFoundException("Product not found or inactive")
        
        # Increment view count
        if increment_view:
            await self.db.execute(
                f"UPDATE products SET view_count = view_count + 1 WHERE id = '{product_id}'"
            )
            await self.db.commit()
        
        # Calculate average rating
        if product.reviews:
            total_rating = sum(review.rating for review in product.reviews)
            product.rating = total_rating / len(product.reviews)
            product.reviews_count = len(product.reviews)
        
        return product
    
    async def list_products(
        self,
        filters: Optional[ProductFilter] = None,
        search: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> Dict[str, Any]:
        """
        List products with filters and pagination
        
        Args:
            filters: Product filters
            search: Search query
            page: Page number
            size: Page size
            
        Returns:
            Paginated product list
        """
        # Base query
        query = select(Product).where(Product.status == "active")
        
        # Apply filters
        if filters:
            query = filters.apply_filters(query)
        
        # Apply search
        if search:
            search_filter = or_(
                Product.title.ilike(f"%{search}%"),
                Product.description.ilike(f"%{search}%"),
                Product.tags.contains([search])
            )
            query = query.where(search_filter)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)
        
        # Apply sorting
        if filters and filters.sort_by:
            if filters.sort_by == "price_asc":
                query = query.order_by(Product.price.asc())
            elif filters.sort_by == "price_desc":
                query = query.order_by(Product.price.desc())
            elif filters.sort_by == "newest":
                query = query.order_by(Product.created_at.desc())
            elif filters.sort_by == "popular":
                query = query.order_by(Product.view_count.desc())
        else:
            query = query.order_by(Product.created_at.desc())
        
        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        
        # Execute query
        result = await self.db.execute(
            query.options(
                selectinload(Product.seller),
                selectinload(Product.category),
                selectinload(Product.brand)
            )
        )
        products = result.scalars().all()
        
        # Calculate total pages
        total_pages = (total + size - 1) // size
        
        return {
            "items": products,
            "total": total,
            "page": page,
            "size": size,
            "pages": total_pages
        }
    
    async def search_products(
        self,
        request: ProductSearchRequest
    ) -> List[Product]:
        """
        Search products with advanced filters
        
        Args:
            request: Search request
            
        Returns:
            List of matching products
        """
        # Use PostgreSQL full-text search
        query = select(Product).where(Product.status == "active")
        
        # Text search
        if request.query:
            # Create search vector
            search_query = func.plainto_tsquery('english', request.query)
            query = query.where(
                Product.search_vector.match(search_query)
            )
            
            # Order by relevance
            if request.sort_by == "relevance":
                query = query.order_by(
                    func.ts_rank(Product.search_vector, search_query).desc()
                )
        
        # Apply filters
        if request.category_id:
            query = query.where(Product.category_id == request.category_id)
        
        if request.brand_id:
            query = query.where(Product.brand_id == request.brand_id)
        
        if request.min_price:
            query = query.where(Product.price >= request.min_price)
        
        if request.max_price:
            query = query.where(Product.price <= request.max_price)
        
        if request.tags:
            query = query.where(Product.tags.contains(request.tags))
        
        if request.in_stock is not None:
            if request.in_stock:
                query = query.where(Product.stock > 0)
            else:
                query = query.where(Product.stock == 0)
        
        # Apply other sorting
        if request.sort_by != "relevance":
            if request.sort_by == "price_asc":
                query = query.order_by(Product.price.asc())
            elif request.sort_by == "price_desc":
                query = query.order_by(Product.price.desc())
            elif request.sort_by == "newest":
                query = query.order_by(Product.created_at.desc())
            elif request.sort_by == "popular":
                query = query.order_by(Product.view_count.desc())
        
        # Execute query
        result = await self.db.execute(query.limit(100))
        return result.scalars().all()
    
    async def update_stock(
        self,
        product_id: uuid.UUID,
        seller_id: uuid.UUID,
        stock: int,
        variant_id: Optional[uuid.UUID] = None
    ) -> Product:
        """
        Update product stock
        
        Args:
            product_id: Product ID
            seller_id: Seller user ID
            stock: New stock quantity
            variant_id: Optional variant ID
            
        Returns:
            Updated product
        """
        # Get product
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        
        if not product:
            raise NotFoundException("Product not found")
        
        if product.seller_id != seller_id:
            raise ForbiddenException("You can only update your own products")
        
        if variant_id:
            # Update variant stock
            variant_result = await self.db.execute(
                select(ProductVariant).where(
                    and_(
                        ProductVariant.id == variant_id,
                        ProductVariant.product_id == product_id
                    )
                )
            )
            variant = variant_result.scalar_one_or_none()
            
            if not variant:
                raise NotFoundException("Product variant not found")
            
            variant.stock = stock
            self.db.add(variant)
        else:
            # Update main product stock
            product.stock = stock
            
            # Update status based on stock
            if stock == 0 and product.track_inventory:
                product.status = "out_of_stock"
            elif product.status == "out_of_stock" and stock > 0:
                product.status = "active"
            
            self.db.add(product)
        
        await self.db.commit()
        await self.db.refresh(product)
        
        # Invalidate cache
        await cache.delete_pattern(f"products:{product_id}:*")
        
        return product
    
    async def delete_product(
        self,
        product_id: uuid.UUID,
        seller_id: uuid.UUID
    ) -> None:
        """
        Delete product (soft delete)
        
        Args:
            product_id: Product ID
            seller_id: Seller user ID
            
        Raises:
            NotFoundException: If product not found
            ForbiddenException: If not the seller
        """
        # Get product
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        
        if not product:
            raise NotFoundException("Product not found")
        
        if product.seller_id != seller_id:
            raise ForbiddenException("You can only delete your own products")
        
        # Soft delete
        product.status = "inactive"
        product.updated_at = datetime.utcnow()
        
        self.db.add(product)
        await self.db.commit()
        
        # Invalidate cache
        await cache.delete_pattern(f"products:{product_id}:*")
        await cache.delete_pattern("products:list:*")
    
    async def get_seller_products(
        self,
        seller_id: uuid.UUID,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> Dict[str, Any]:
        """
        Get products for a specific seller
        
        Args:
            seller_id: Seller user ID
            status: Optional status filter
            page: Page number
            size: Page size
            
        Returns:
            Paginated product list
        """
        query = select(Product).where(Product.seller_id == seller_id)
        
        if status:
            query = query.where(Product.status == status)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)
        
        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size).order_by(Product.created_at.desc())
        
        # Execute query
        result = await self.db.execute(query)
        products = result.scalars().all()
        
        # Calculate total pages
        total_pages = (total + size - 1) // size
        
        return {
            "items": products,
            "total": total,
            "page": page,
            "size": size,
            "pages": total_pages
        }
    
    async def bulk_upload_products(
        self,
        seller_id: uuid.UUID,
        products_data: List[ProductCreate]
    ) -> List[Product]:
        """
        Bulk upload products
        
        Args:
            seller_id: Seller user ID
            products_data: List of product data
            
        Returns:
            List of created products
        """
        created_products = []
        
        for product_data in products_data:
            try:
                product = await self.create_product(seller_id, product_data)
                created_products.append(product)
            except Exception as e:
                # Log error but continue with other products
                print(f"Error creating product {product_data.title}: {str(e)}")
        
        return created_products
