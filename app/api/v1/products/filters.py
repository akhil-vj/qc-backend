"""
Product filtering logic
"""

from dataclasses import dataclass
from typing import Optional, List
from decimal import Decimal
from sqlalchemy import and_, or_
from sqlalchemy.orm import Query
import uuid

from app.models import Product

@dataclass
class ProductFilter:
    """Product filter parameters"""
    category_id: Optional[uuid.UUID] = None
    brand_id: Optional[uuid.UUID] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    in_stock: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_digital: Optional[bool] = None
    tags: Optional[List[str]] = None
    seller_id: Optional[uuid.UUID] = None
    status: Optional[str] = None
    sort_by: Optional[str] = None
    
    def apply_filters(self, query: Query) -> Query:
        """Apply filters to query"""
        conditions = []
        
        if self.category_id:
            conditions.append(Product.category_id == self.category_id)
        
        if self.brand_id:
            conditions.append(Product.brand_id == self.brand_id)
        
        if self.min_price is not None:
            conditions.append(Product.price >= self.min_price)
        
        if self.max_price is not None:
            conditions.append(Product.price <= self.max_price)
        
        if self.in_stock is not None:
            if self.in_stock:
                conditions.append(Product.stock > 0)
            else:
                conditions.append(Product.stock == 0)
        
        if self.is_featured is not None:
            conditions.append(Product.is_featured == self.is_featured)
        
        if self.is_digital is not None:
            conditions.append(Product.is_digital == self.is_digital)
        
        if self.tags:
            # Product must have all specified tags
            for tag in self.tags:
                conditions.append(Product.tags.contains([tag]))
        
        if self.seller_id:
            conditions.append(Product.seller_id == self.seller_id)
        
        if self.status:
            conditions.append(Product.status == self.status)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        return query
