"""Product model using base mixins"""

from sqlalchemy import Column, String, Text, Numeric, Integer, Boolean, JSON, ForeignKey, Index, CheckConstraint, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB, TSVECTOR

from .base import Base, TimestampedModel, UUIDModel, StatusModel, SluggedModel

class Product(Base, TimestampedModel, UUIDModel, StatusModel, SluggedModel):
    """Product model with status and slug support"""
    
    __tablename__ = "products"
    
    # Basic info
    name = Column(String(255), nullable=False, index=True)  # Add name field
    title = Column(String(200), nullable=False, index=True)  # Keep for compatibility
    description = Column(Text, nullable=False)
    sku = Column(String(50), unique=True, index=True)
    
    # Categorization
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    brand = Column(String(100), index=True)
    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)  # keeping for compatibility
    tags = Column(ARRAY(String), default=[])
    
    # Pricing
    price = Column(Numeric(10, 2), nullable=False, index=True)
    mrp = Column(Numeric(10, 2))
    cost_price = Column(Numeric(10, 2))
    discount_percentage = Column(Numeric(5, 2), default=0)
    
    # Inventory
    stock_quantity = Column(Integer, default=0, nullable=False)  # Add stock_quantity
    stock = Column(Integer, default=0, nullable=False)  # Keep for compatibility
    low_stock_threshold = Column(Integer, default=10)
    min_order_quantity = Column(Integer, default=1)
    max_order_quantity = Column(Integer, nullable=True)
    track_inventory = Column(Boolean, default=True)
    
    # Features and Stats (combined)
    is_featured = Column(Boolean, default=False, index=True)
    view_count = Column(Integer, default=0, nullable=False)
    rating = Column(Numeric(3, 2), nullable=True)
    review_count = Column(Integer, default=0, nullable=False)
    purchase_count = Column(Integer, default=0)
    wishlist_count = Column(Integer, default=0)
    trending_score = Column(Numeric(5, 2), default=0)
    quality_score = Column(Numeric(5, 2), default=0)
    
    # Seller info
    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Media
    primary_image = Column(String(500))
    thumbnail = Column(String(500), nullable=True)  # keeping for compatibility
    images = Column(ARRAY(String), default=[])
    video_url = Column(String(500))
    
    # Product details
    weight = Column(Numeric(10, 3), nullable=True)  # in kg
    dimensions = Column(JSONB, nullable=True)  # {length, width, height, unit}
    
    # Attributes
    attributes = Column(JSON, default={})
    specifications = Column(JSON, default={})
    
    # Policies
    shipping_info = Column(JSONB, default={})
    return_policy = Column(JSONB, default={})
    warranty_info = Column(JSONB, default={})
    
    # SEO (enhanced)
    meta_title = Column(String(255))
    meta_description = Column(String(500))
    meta_keywords = Column(ARRAY(String), default=[])
    
    # Flags
    is_digital = Column(Boolean, default=False)
    requires_shipping = Column(Boolean, default=True)
    is_giftable = Column(Boolean, default=True)
    
    # AI/ML features
    ai_category_suggestion = Column(String(255), nullable=True)  # keeping for compatibility
    ai_categorized = Column(Boolean, default=False)
    trending_score = Column(Numeric(5, 2), default=0)
    quality_score = Column(Numeric(5, 2), default=0)
    search_vector = Column(TSVECTOR, nullable=True)
    
    # Publishing
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional data
    product_metadata = Column(JSONB, default={})
    
    # Relationships
    category = relationship("Category", back_populates="products")
    brand = relationship("Brand", back_populates="products")
    seller = relationship("User", back_populates="products")
    reviews = relationship("Review", back_populates="product", cascade="all, delete-orphan")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="product")
    cart_items = relationship("CartItem", back_populates="product")
    wishlist_items = relationship("WishlistItem", back_populates="product")
    flash_sale_products = relationship("FlashSaleProduct", back_populates="product")
    price_history = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("price > 0", name="check_positive_price"),
        CheckConstraint("stock >= 0", name="check_non_negative_stock"),
        CheckConstraint("min_order_quantity > 0", name="check_positive_min_order"),
        Index("idx_products_seller_status", "seller_id", "status"),
        Index("idx_products_category_status", "category_id", "status"),
        Index("idx_products_price_status", "price", "status"),
        Index("idx_products_trending", "trending_score", "status"),
        Index("idx_products_search_vector", "search_vector", postgresql_using="gin"),
    )
    
    @property
    def is_in_stock(self):
        """Check if product is in stock"""
        return self.stock > 0 if self.track_inventory else True
    
    @property
    def final_price(self):
        """Calculate final price after discount"""
        if self.discount_percentage:
            discount = self.price * (self.discount_percentage / 100)
            return self.price - discount
        return self.price

class ProductVariant(Base, TimestampedModel, UUIDModel):
    """Product variants (size, color, etc.)"""
    
    __tablename__ = "product_variants"
    
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    sku = Column(String(100), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    
    # Variant attributes
    attributes = Column(JSONB, nullable=False)  # {color: "Red", size: "XL"}
    
    # Pricing (if different from main product)
    price = Column(Numeric(10, 2), nullable=True)
    mrp = Column(Numeric(10, 2), nullable=True)
    
    # Inventory
    stock = Column(Integer, default=0)
    
    # Media
    image = Column(String(500), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    product = relationship("Product", back_populates="variants")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("stock >= 0", name="check_variant_non_negative_stock"),
        Index("idx_product_variants_product_active", "product_id", "is_active"),
    )

class ProductImage(Base, TimestampedModel, UUIDModel):
    """Additional product images"""
    
    __tablename__ = "product_images"
    
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    url = Column(String(500), nullable=False)
    alt_text = Column(String(255), nullable=True)
    display_order = Column(Integer, default=0)
    is_primary = Column(Boolean, default=False)
    
    # Relationships
    product = relationship("Product")
