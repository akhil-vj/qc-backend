"""
Cart service layer
Handles shopping cart business logic
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from sqlalchemy.orm import selectinload
import uuid

from app.models import CartItem, Product, ProductVariant, User, Coupon
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    InsufficientStockException
)
from app.core.cache import cache, invalidate_cache
from .schemas import CartItemCreate, CartItemUpdate, CartResponse

class CartService:
    """Shopping cart service"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_cart(
        self,
        user_id: Optional[uuid.UUID] = None,
        session_id: Optional[str] = None
    ) -> CartResponse:
        """
        Get cart for user or session
        
        Args:
            user_id: User ID for authenticated users
            session_id: Session ID for anonymous users
            
        Returns:
            Complete cart with calculations
        """
        if not user_id and not session_id:
            raise BadRequestException("Either user_id or session_id is required")
        
        # Build query
        conditions = []
        if user_id:
            conditions.append(CartItem.user_id == user_id)
        if session_id:
            conditions.append(CartItem.session_id == session_id)
        
        # Get cart items
        result = await self.db.execute(
            select(CartItem)
            .options(
                selectinload(CartItem.product).selectinload(Product.seller),
                selectinload(CartItem.variant)
            )
            .where(or_(*conditions))
            .order_by(CartItem.created_at.desc())
        )
        cart_items = result.scalars().all()
        
        # Separate active and saved items
        active_items = []
        saved_items = []
        
        for item in cart_items:
            # Check product availability
            is_available = (
                item.product.status == "active" and
                (not item.product.track_inventory or item.product.stock >= item.quantity)
            )
            
            # Create response item
            response_item = {
                "id": item.id,
                "product_id": item.product_id,
                "variant_id": item.variant_id,
                "quantity": item.quantity,
                "price": item.price,
                "saved_for_later": item.saved_for_later,
                "created_at": item.created_at,
                "product_title": item.product.title,
                "product_slug": item.product.slug,
                "product_thumbnail": item.product.thumbnail,
                "product_price": item.product.price,
                "product_final_price": item.product.final_price,
                "product_stock": item.product.stock,
                "variant_name": item.variant.name if item.variant else None,
                "subtotal": item.price * item.quantity,
                "is_available": is_available
            }
            
            if item.saved_for_later:
                saved_items.append(response_item)
            else:
                active_items.append(response_item)
        
        # Calculate totals
        subtotal = sum(item["subtotal"] for item in active_items if item["is_available"])
        
        # Apply tax (simplified - 18% GST)
        tax = subtotal * Decimal("0.18")
        
        # Calculate shipping (free above ₹500)
        shipping_fee = Decimal("0.00") if subtotal >= 500 else Decimal("40.00")
        
        # Total
        total = subtotal + tax + shipping_fee
        
        return CartResponse(
            items=active_items,
            saved_items=saved_items,
            total_items=len(active_items),
            subtotal=subtotal,
            discount=Decimal("0.00"),
            tax=tax,
            shipping_fee=shipping_fee,
            total=total
        )
    
    async def add_to_cart(
        self,
        user_id: Optional[uuid.UUID],
        session_id: Optional[str],
        item_data: CartItemCreate
    ) -> CartItem:
        """
        Add item to cart
        
        Args:
            user_id: User ID for authenticated users
            session_id: Session ID for anonymous users
            item_data: Item to add
            
        Returns:
            Created or updated cart item
            
        Raises:
            NotFoundException: If product not found
            InsufficientStockException: If not enough stock
        """
        # Get product
        result = await self.db.execute(
            select(Product)
            .where(Product.id == item_data.product_id)
        )
        product = result.scalar_one_or_none()
        
        if not product or product.status != "active":
            raise NotFoundException("Product not found or inactive")
        
        # Check stock
        if product.track_inventory and product.stock < item_data.quantity:
            raise InsufficientStockException(product.title, product.stock)
        
        # Check for existing item
        conditions = [
            CartItem.product_id == item_data.product_id,
            CartItem.saved_for_later == False
        ]
        
        if user_id:
            conditions.append(CartItem.user_id == user_id)
        else:
            conditions.append(CartItem.session_id == session_id)
        
        if item_data.variant_id:
            conditions.append(CartItem.variant_id == item_data.variant_id)
        else:
            conditions.append(CartItem.variant_id.is_(None))
        
        existing = await self.db.execute(
            select(CartItem).where(and_(*conditions))
        )
        existing_item = existing.scalar_one_or_none()
        
        if existing_item:
            # Update quantity
            new_quantity = existing_item.quantity + item_data.quantity
            
            # Check stock for new quantity
            if product.track_inventory and product.stock < new_quantity:
                raise InsufficientStockException(product.title, product.stock)
            
            existing_item.quantity = new_quantity
            existing_item.price = product.final_price
            
            self.db.add(existing_item)
            await self.db.commit()
            await self.db.refresh(existing_item)
            
            return existing_item
        else:
            # Create new item
            cart_item = CartItem(
                user_id=user_id,
                session_id=session_id,
                product_id=item_data.product_id,
                variant_id=item_data.variant_id,
                quantity=item_data.quantity,
                price=product.final_price
            )
            
            self.db.add(cart_item)
            await self.db.commit()
            await self.db.refresh(cart_item)
            
            return cart_item
    
    async def update_cart_item(
        self,
        user_id: Optional[uuid.UUID],
        session_id: Optional[str],
        item_id: uuid.UUID,
        update_data: CartItemUpdate
    ) -> CartItem:
        """
        Update cart item quantity
        
        Args:
            user_id: User ID
            session_id: Session ID
            item_id: Cart item ID
            update_data: Update data
            
        Returns:
            Updated cart item
            
        Raises:
            NotFoundException: If item not found
            InsufficientStockException: If not enough stock
        """
        # Get cart item
        conditions = [CartItem.id == item_id]
        
        if user_id:
            conditions.append(CartItem.user_id == user_id)
        else:
            conditions.append(CartItem.session_id == session_id)
        
        result = await self.db.execute(
            select(CartItem)
            .options(selectinload(CartItem.product))
            .where(and_(*conditions))
        )
        cart_item = result.scalar_one_or_none()
        
        if not cart_item:
            raise NotFoundException("Cart item not found")
        
        # Check stock
        product = cart_item.product
        if product.track_inventory and product.stock < update_data.quantity:
            raise InsufficientStockException(product.title, product.stock)
        
        # Update quantity
        cart_item.quantity = update_data.quantity
        cart_item.price = product.final_price
        
        self.db.add(cart_item)
        await self.db.commit()
        await self.db.refresh(cart_item)
        
        return cart_item
    
    async def remove_from_cart(
        self,
        user_id: Optional[uuid.UUID],
        session_id: Optional[str],
        item_id: uuid.UUID
    ) -> None:
        """
        Remove item from cart
        
        Args:
            user_id: User ID
            session_id: Session ID
            item_id: Cart item ID
            
        Raises:
            NotFoundException: If item not found
        """
        # Build conditions
        conditions = [CartItem.id == item_id]
        
        if user_id:
            conditions.append(CartItem.user_id == user_id)
        else:
            conditions.append(CartItem.session_id == session_id)
        
        # Delete item
        result = await self.db.execute(
            delete(CartItem).where(and_(*conditions))
        )
        
        if result.rowcount == 0:
            raise NotFoundException("Cart item not found")
        
        await self.db.commit()
    
    async def save_for_later(
        self,
        user_id: uuid.UUID,
        item_id: uuid.UUID
    ) -> CartItem:
        """
        Move item to saved for later
        
        Args:
            user_id: User ID
            item_id: Cart item ID
            
        Returns:
            Updated cart item
            
        Raises:
            NotFoundException: If item not found
        """
        # Get cart item
        result = await self.db.execute(
            select(CartItem)
            .where(and_(
                CartItem.id == item_id,
                CartItem.user_id == user_id,
                CartItem.saved_for_later == False
            ))
        )
        cart_item = result.scalar_one_or_none()
        
        if not cart_item:
            raise NotFoundException("Cart item not found")
        
        # Update saved status
        cart_item.saved_for_later = True
        
        self.db.add(cart_item)
        await self.db.commit()
        await self.db.refresh(cart_item)
        
        return cart_item
    
    async def move_to_cart(
        self,
        user_id: uuid.UUID,
        item_id: uuid.UUID
    ) -> CartItem:
        """
        Move item from saved to cart
        
        Args:
            user_id: User ID
            item_id: Cart item ID
            
        Returns:
            Updated cart item
            
        Raises:
            NotFoundException: If item not found
        """
        # Get saved item
        result = await self.db.execute(
            select(CartItem)
            .options(selectinload(CartItem.product))
            .where(and_(
                CartItem.id == item_id,
                CartItem.user_id == user_id,
                CartItem.saved_for_later == True
            ))
        )
        cart_item = result.scalar_one_or_none()
        
        if not cart_item:
            raise NotFoundException("Saved item not found")
        
        # Check if product is still available
        product = cart_item.product
        if product.status != "active":
            raise BadRequestException("Product is no longer available")
        
        # Check stock
        if product.track_inventory and product.stock < cart_item.quantity:
            # Adjust quantity to available stock
            cart_item.quantity = min(cart_item.quantity, product.stock)
        
        # Update saved status
        cart_item.saved_for_later = False
        cart_item.price = product.final_price
        
        self.db.add(cart_item)
        await self.db.commit()
        await self.db.refresh(cart_item)
        
        return cart_item
    
    async def clear_cart(
        self,
        user_id: Optional[uuid.UUID],
        session_id: Optional[str]
    ) -> None:
        """
        Clear all items from cart
        
        Args:
            user_id: User ID
            session_id: Session ID
        """
        conditions = [CartItem.saved_for_later == False]
        
        if user_id:
            conditions.append(CartItem.user_id == user_id)
        else:
            conditions.append(CartItem.session_id == session_id)
        
        await self.db.execute(
            delete(CartItem).where(and_(*conditions))
        )
        await self.db.commit()
    
    async def merge_carts(
        self,
        user_id: uuid.UUID,
        session_id: str
    ) -> None:
        """
        Merge session cart with user cart on login
        
        Args:
            user_id: User ID
            session_id: Session ID
        """
        # Get session cart items
        result = await self.db.execute(
            select(CartItem)
            .where(CartItem.session_id == session_id)
        )
        session_items = result.scalars().all()
        
        for item in session_items:
            # Check if user already has this item
            existing = await self.db.execute(
                select(CartItem)
                .where(and_(
                    CartItem.user_id == user_id,
                    CartItem.product_id == item.product_id,
                    CartItem.variant_id == item.variant_id,
                    CartItem.saved_for_later == item.saved_for_later
                ))
            )
            existing_item = existing.scalar_one_or_none()
            
            if existing_item:
                # Merge quantities
                existing_item.quantity += item.quantity
                self.db.add(existing_item)
                await self.db.delete(item)
            else:
                # Transfer to user
                item.user_id = user_id
                item.session_id = None
                self.db.add(item)
        
        await self.db.commit()
    
    async def apply_coupon(
        self,
        user_id: uuid.UUID,
        coupon_code: str
    ) -> Dict[str, Any]:
        """
        Apply coupon to cart
        
        Args:
            user_id: User ID
            coupon_code: Coupon code
            
        Returns:
            Coupon details and discount amount
            
        Raises:
            NotFoundException: If coupon not found
            BadRequestException: If coupon not valid
        """
        # Get coupon
        result = await self.db.execute(
            select(Coupon)
            .where(Coupon.code == coupon_code.upper())
        )
        coupon = result.scalar_one_or_none()
        
        if not coupon:
            raise NotFoundException("Invalid coupon code")
        
        if not coupon.is_valid:
            raise BadRequestException("Coupon is expired or inactive")
        
        # Get cart total
        cart = await self.get_cart(user_id=user_id)
        
        # Check minimum order value
        if coupon.min_order_value and cart.subtotal < coupon.min_order_value:
            raise BadRequestException(
                f"Minimum order value of ₹{coupon.min_order_value} required"
            )
        
        # Calculate discount
        if coupon.discount_type == "percentage":
            discount = cart.subtotal * (coupon.discount_value / 100)
        else:
            discount = coupon.discount_value
        
        # Apply max discount limit
        if coupon.max_discount:
            discount = min(discount, coupon.max_discount)
        
        return {
            "coupon_code": coupon.code,
            "discount_amount": discount,
            "description": coupon.description
        }
