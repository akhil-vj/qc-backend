"""
Cart service for managing cart operations
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import selectinload

from app.models.cart import CartItem
from app.models.product import Product, ProductVariant
from app.models.user import User
from app.core.exceptions import NotFoundException, BadRequestException


class CartService:
    """
    Service for managing cart operations
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def add_to_cart(
        self, 
        user_id: int, 
        product_id: int, 
        quantity: int = 1,
        variant_id: Optional[int] = None
    ) -> CartItem:
        """
        Add item to cart or update quantity if exists
        """
        try:
            # Check if product exists
            product_result = await self.db.execute(
                select(Product).where(Product.id == product_id)
            )
            product = product_result.scalar_one_or_none()
            if not product:
                raise NotFoundException("Product not found")
            
            # Check if item already exists in cart
            query = select(CartItem).where(
                and_(
                    CartItem.user_id == user_id,
                    CartItem.product_id == product_id
                )
            )
            
            if variant_id:
                query = query.where(CartItem.variant_id == variant_id)
            else:
                query = query.where(CartItem.variant_id.is_(None))
            
            result = await self.db.execute(query)
            existing_item = result.scalar_one_or_none()
            
            if existing_item:
                # Update quantity
                existing_item.quantity += quantity
                await self.db.commit()
                return existing_item
            else:
                # Create new cart item
                cart_item = CartItem(
                    user_id=user_id,
                    product_id=product_id,
                    variant_id=variant_id,
                    quantity=quantity
                )
                self.db.add(cart_item)
                await self.db.commit()
                await self.db.refresh(cart_item)
                return cart_item
                
        except Exception as e:
            await self.db.rollback()
            raise BadRequestException(f"Failed to add item to cart: {str(e)}")
    
    async def get_cart_items(self, user_id: int) -> List[CartItem]:
        """
        Get all items in user's cart
        """
        try:
            result = await self.db.execute(
                select(CartItem)
                .options(
                    selectinload(CartItem.product),
                    selectinload(CartItem.variant)
                )
                .where(CartItem.user_id == user_id)
                .order_by(CartItem.created_at.desc())
            )
            return result.scalars().all()
            
        except Exception:
            return []
    
    async def update_cart_item(
        self, 
        user_id: int, 
        item_id: int, 
        quantity: int
    ) -> Optional[CartItem]:
        """
        Update cart item quantity
        """
        try:
            result = await self.db.execute(
                select(CartItem).where(
                    and_(
                        CartItem.id == item_id,
                        CartItem.user_id == user_id
                    )
                )
            )
            cart_item = result.scalar_one_or_none()
            
            if not cart_item:
                raise NotFoundException("Cart item not found")
            
            if quantity <= 0:
                await self.db.delete(cart_item)
            else:
                cart_item.quantity = quantity
            
            await self.db.commit()
            return cart_item if quantity > 0 else None
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, NotFoundException):
                raise
            raise BadRequestException(f"Failed to update cart item: {str(e)}")
    
    async def remove_from_cart(
        self, 
        user_id: int, 
        item_id: int
    ) -> bool:
        """
        Remove item from cart
        """
        try:
            result = await self.db.execute(
                select(CartItem).where(
                    and_(
                        CartItem.id == item_id,
                        CartItem.user_id == user_id
                    )
                )
            )
            cart_item = result.scalar_one_or_none()
            
            if not cart_item:
                raise NotFoundException("Cart item not found")
            
            await self.db.delete(cart_item)
            await self.db.commit()
            return True
            
        except Exception as e:
            await self.db.rollback()
            if isinstance(e, NotFoundException):
                raise
            raise BadRequestException(f"Failed to remove cart item: {str(e)}")
    
    async def clear_cart(self, user_id: int) -> bool:
        """
        Clear all items from user's cart
        """
        try:
            await self.db.execute(
                delete(CartItem).where(CartItem.user_id == user_id)
            )
            await self.db.commit()
            return True
            
        except Exception:
            await self.db.rollback()
            return False
    
    async def get_cart_total(self, user_id: int) -> Dict[str, Any]:
        """
        Calculate cart totals
        """
        try:
            cart_items = await self.get_cart_items(user_id)
            
            subtotal = 0
            total_items = 0
            
            for item in cart_items:
                if item.product:
                    price = item.variant.price if item.variant else item.product.price
                    subtotal += float(price) * item.quantity
                    total_items += item.quantity
            
            return {
                "subtotal": subtotal,
                "total_items": total_items,
                "tax": subtotal * 0.18,  # 18% tax
                "shipping": 50 if subtotal < 500 else 0,  # Free shipping over 500
                "total": subtotal + (subtotal * 0.18) + (50 if subtotal < 500 else 0)
            }
            
        except Exception:
            return {
                "subtotal": 0,
                "total_items": 0,
                "tax": 0,
                "shipping": 0,
                "total": 0
            }
