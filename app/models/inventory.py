"""
Inventory management models and utilities
"""

from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models.product import Product, ProductVariant


class InventoryManager:
    """
    Manages inventory operations for products and variants
    """
    
    async def check_availability(
        self, 
        db: AsyncSession, 
        product_id: int, 
        variant_id: Optional[int] = None,
        quantity: int = 1
    ) -> bool:
        """
        Check if requested quantity is available for a product/variant
        """
        try:
            if variant_id:
                # Check variant stock
                result = await db.execute(
                    select(ProductVariant).where(
                        ProductVariant.id == variant_id,
                        ProductVariant.product_id == product_id
                    )
                )
                variant = result.scalar_one_or_none()
                if not variant:
                    return False
                return variant.stock_quantity >= quantity
            else:
                # Check product stock
                result = await db.execute(
                    select(Product).where(Product.id == product_id)
                )
                product = result.scalar_one_or_none()
                if not product:
                    return False
                return product.stock_quantity >= quantity
        except Exception:
            return False
    
    async def reserve_stock(
        self, 
        db: AsyncSession, 
        order_id: int, 
        items: List[Dict]
    ) -> bool:
        """
        Reserve stock for order items
        """
        try:
            for item in items:
                product_id = item.get('product_id')
                variant_id = item.get('variant_id')
                quantity = item.get('quantity', 1)
                
                if variant_id:
                    # Reserve variant stock
                    await db.execute(
                        update(ProductVariant)
                        .where(ProductVariant.id == variant_id)
                        .values(stock_quantity=ProductVariant.stock_quantity - quantity)
                    )
                else:
                    # Reserve product stock
                    await db.execute(
                        update(Product)
                        .where(Product.id == product_id)
                        .values(stock_quantity=Product.stock_quantity - quantity)
                    )
            
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            return False
    
    async def confirm_reservation(self, db: AsyncSession, order_id: int) -> bool:
        """
        Confirm stock reservation for an order
        """
        # In a more complex system, this would mark reservations as confirmed
        # For now, just return True as stock is already reserved
        return True
    
    async def complete_order(self, db: AsyncSession, order_id: int) -> bool:
        """
        Complete order and finalize inventory changes
        """
        # In a more complex system, this would handle final inventory updates
        # For now, just return True as stock is already deducted
        return True
    
    async def cancel_reservation(self, db: AsyncSession, order_id: int) -> bool:
        """
        Cancel stock reservation and return items to inventory
        """
        # In a real implementation, this would restore reserved stock
        # For now, just return True
        return True
    
    async def get_low_stock_products(
        self, 
        db: AsyncSession, 
        threshold: int = 10
    ) -> List[Product]:
        """
        Get products with stock below threshold
        """
        try:
            result = await db.execute(
                select(Product)
                .where(Product.stock_quantity <= threshold)
                .options(selectinload(Product.variants))
            )
            return result.scalars().all()
        except Exception:
            return []
    
    async def update_stock(
        self, 
        db: AsyncSession, 
        product_id: int, 
        quantity: int,
        variant_id: Optional[int] = None
    ) -> bool:
        """
        Update stock quantity for a product or variant
        """
        try:
            if variant_id:
                await db.execute(
                    update(ProductVariant)
                    .where(ProductVariant.id == variant_id)
                    .values(stock_quantity=quantity)
                )
            else:
                await db.execute(
                    update(Product)
                    .where(Product.id == product_id)
                    .values(stock_quantity=quantity)
                )
            
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            return False


# Global inventory manager instance
inventory_manager = InventoryManager()
