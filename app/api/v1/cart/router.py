"""Complete cart router with session handling and coupon application"""

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from app.core.database import get_db
from app.api.v1.auth.dependencies import get_current_user_optional, get_current_user
from app.services.cart_service import CartService
from app.services.coupon_service import CouponService
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartResponse

router = APIRouter(prefix="/cart", tags=["cart"])

@router.get("/", response_model=CartResponse)
async def get_cart(
    request: Request,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """Get cart (supports both authenticated and session-based)"""
    service = CartService(db)
    
    if current_user:
        # Authenticated user cart
        cart = await service.get_user_cart(current_user["id"])
    else:
        # Session-based cart
        session_id = request.session.get("session_id")
        if not session_id:
            return CartResponse(items=[], total_items=0, subtotal=0, total=0)
            
        cart = await service.get_session_cart(session_id)
        
    return cart

@router.post("/add")
async def add_to_cart(
    item_data: CartItemCreate,
    request: Request,
    response: Response,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """Add item to cart"""
    service = CartService(db)
    
    if current_user:
        # Add to user cart
        cart_item = await service.add_to_cart(
            user_id=current_user["id"],
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            variant_id=item_data.variant_id
        )
    else:
        # Session-based cart
        session_id = request.session.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            request.session["session_id"] = session_id
            
        cart_item = await service.add_to_session_cart(
            session_id=session_id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            variant_id=item_data.variant_id
        )
        
    return {"message": "Item added to cart", "cart_item": cart_item}

@router.put("/update/{item_id}")
async def update_cart_item(
    item_id: uuid.UUID,
    update_data: CartItemUpdate,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """Update cart item quantity"""
    service = CartService(db)
    
    if current_user:
        updated_item = await service.update_cart_item(
            user_id=current_user["id"],
            item_id=str(item_id),
            quantity=update_data.quantity
        )
    else:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to update cart"
        )
        
    return updated_item

@router.delete("/remove/{item_id}")
async def remove_from_cart(
    item_id: uuid.UUID,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """Remove item from cart"""
    service = CartService(db)
    
    if current_user:
        await service.remove_from_cart(
            user_id=current_user["id"],
            item_id=str(item_id)
        )
    else:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to remove from cart"
        )
        
    return {"message": "Item removed from cart"}

@router.post("/clear")
async def clear_cart(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Clear entire cart"""
    service = CartService(db)
    
    await service.clear_cart(current_user["id"])
    
    return {"message": "Cart cleared"}

@router.post("/merge")
async def merge_carts(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Merge session cart with user cart after login"""
    session_id = request.session.get("session_id")
    if not session_id:
        return {"message": "No session cart to merge"}
        
    service = CartService(db)
    
    merged_count = await service.merge_session_cart(
        session_id=session_id,
        user_id=current_user["id"]
    )
    
    # Clear session
    request.session.pop("session_id", None)
    
    return {
        "message": f"Merged {merged_count} items into your cart",
        "items_merged": merged_count
    }

@router.post("/apply-coupon")
async def apply_coupon(
    coupon_code: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Apply coupon to cart"""
    cart_service = CartService(db)
    coupon_service = CouponService(db)
    
    # Get cart
    cart = await cart_service.get_user_cart(current_user["id"])
    if not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")
        
    # Validate coupon
    coupon = await coupon_service.validate_coupon(
        code=coupon_code,
        user_id=current_user["id"],
        cart_value=cart.subtotal
    )
    
    if not coupon["is_valid"]:
        raise HTTPException(status_code=400, detail=coupon["error"])
        
    # Apply coupon to cart
    discount = await coupon_service.calculate_discount(
        coupon=coupon["coupon"],
        cart_value=cart.subtotal,
        items=cart.items
    )
    
    # Store applied coupon in cart
    await cart_service.apply_coupon(
        user_id=current_user["id"],
        coupon_id=coupon["coupon"].id,
        discount_amount=discount["amount"]
    )
    
    return {
        "coupon_applied": True,
        "coupon_code": coupon_code,
        "discount_amount": discount["amount"],
        "discount_percentage": discount["percentage"],
        "final_amount": cart.subtotal - discount["amount"]
    }

@router.delete("/remove-coupon")
async def remove_coupon(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove applied coupon from cart"""
    service = CartService(db)
    
    await service.remove_coupon(current_user["id"])
    
    return {"message": "Coupon removed"}

@router.post("/save-for-later/{item_id}")
async def save_for_later(
    item_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Move item to saved for later"""
    service = CartService(db)
    
    await service.save_for_later(
        user_id=current_user["id"],
        item_id=str(item_id)
    )
    
    return {"message": "Item saved for later"}

@router.post("/move-to-cart/{item_id}")
async def move_to_cart(
    item_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Move item from saved to cart"""
    service = CartService(db)
    
    await service.move_to_cart(
        user_id=current_user["id"],
        item_id=str(item_id)
    )
    
    return {"message": "Item moved to cart"}

@router.get("/saved")
async def get_saved_items(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get saved for later items"""
    service = CartService(db)
    
    saved_items = await service.get_saved_items(current_user["id"])
    
    return saved_items

@router.post("/validate")
async def validate_cart(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Validate cart before checkout"""
    service = CartService(db)
    
    validation = await service.validate_cart(current_user["id"])
    
    if not validation["is_valid"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Cart validation failed",
                "errors": validation["errors"]
            }
        )
        
    return {
        "is_valid": True,
        "cart_summary": validation["summary"]
    }



# """
# Cart API routes
# """

# from fastapi import APIRouter, Depends, status, Header
# from sqlalchemy.ext.asyncio import AsyncSession
# from typing import Optional
# import uuid

# from app.core.database import get_db
# from app.core.security import get_current_user
# from app.api.v1.auth.dependencies import get_current_user_optional
# from .schemas import (
#     CartItemCreate,
#     CartItemUpdate,
#     CartItemResponse,
#     CartResponse,
#     MoveToCartRequest,
#     ApplyCouponRequest,
#     CartMergeRequest
# )
# from .services import CartService

# router = APIRouter()

# @router.get(
#     "/",
#     response_model=CartResponse,
#     summary="Get cart",
#     description="Get current cart for user or session"
# )
# async def get_cart(
#     current_user: Optional[dict] = Depends(get_current_user_optional),
#     session_id: Optional[str] = Header(None, alias="X-Session-ID"),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get cart contents"""
#     service = CartService(db)
    
#     user_id = uuid.UUID(current_user["id"]) if current_user else None
    
#     cart = await service.get_cart(
#         user_id=user_id,
#         session_id=session_id
#     )
    
#     return cart

# @router.post(
#     "/items",
#     response_model=CartItemResponse,
#     status_code=status.HTTP_201_CREATED,
#     summary="Add to cart",
#     description="Add product to shopping cart"
# )
# async def add_to_cart(
#     item_data: CartItemCreate,
#     current_user: Optional[dict] = Depends(get_current_user_optional),
#     session_id: Optional[str] = Header(None, alias="X-Session-ID"),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Add item to cart"""
#     service = CartService(db)
    
#     user_id = uuid.UUID(current_user["id"]) if current_user else None
    
#     cart_item = await service.add_to_cart(
#         user_id=user_id,
#         session_id=session_id,
#         item_data=item_data
#     )
    
#     # Get full item details for response
#     await db.refresh(cart_item, ["product", "variant"])
    
#     return CartItemResponse(
#         id=cart_item.id,
#         product_id=cart_item.product_id,
#         variant_id=cart_item.variant_id,
#         quantity=cart_item.quantity,
#         price=cart_item.price,
#         saved_for_later=cart_item.saved_for_later,
#         created_at=cart_item.created_at,
#         product_title=cart_item.product.title,
#         product_slug=cart_item.product.slug,
#         product_thumbnail=cart_item.product.thumbnail,
#         product_price=cart_item.product.price,
#         product_final_price=cart_item.product.final_price,
#         product_stock=cart_item.product.stock,
#         variant_name=cart_item.variant.name if cart_item.variant else None,
#         subtotal=cart_item.price * cart_item.quantity,
#         is_available=cart_item.product.is_in_stock
#     )

# @router.put(
#     "/items/{item_id}",
#     response_model=CartItemResponse,
#     summary="Update cart item",
#     description="Update quantity of cart item"
# )
# async def update_cart_item(
#     item_id: uuid.UUID,
#     update_data: CartItemUpdate,
#     current_user: Optional[dict] = Depends(get_current_user_optional),
#     session_id: Optional[str] = Header(None, alias="X-Session-ID"),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update cart item quantity"""
#     service = CartService(db)
    
#     user_id = uuid.UUID(current_user["id"]) if current_user else None
    
#     cart_item = await service.update_cart_item(
#         user_id=user_id,
#         session_id=session_id,
#         item_id=item_id,
#         update_data=update_data
#     )
    
#     # Get full item details for response
#     await db.refresh(cart_item, ["product", "variant"])
    
#     return CartItemResponse(
#         id=cart_item.id,
#         product_id=cart_item.product_id,
#         variant_id=cart_item.variant_id,
#         quantity=cart_item.quantity,
#         price=cart_item.price,
#         saved_for_later=cart_item.saved_for_later,
#         created_at=cart_item.created_at,
#         product_title=cart_item.product.title,
#         product_slug=cart_item.product.slug,
#         product_thumbnail=cart_item.product.thumbnail,
#         product_price=cart_item.product.price,
#         product_final_price=cart_item.product.final_price,
#         product_stock=cart_item.product.stock,
#         variant_name=cart_item.variant.name if cart_item.variant else None,
#         subtotal=cart_item.price * cart_item.quantity,
#         is_available=cart_item.product.is_in_stock
#     )

# @router.delete(
#     "/items/{item_id}",
#     status_code=status.HTTP_204_NO_CONTENT,
#     summary="Remove from cart",
#     description="Remove item from cart"
# )
# async def remove_from_cart(
#     item_id: uuid.UUID,
#     current_user: Optional[dict] = Depends(get_current_user_optional),
#     session_id: Optional[str] = Header(None, alias="X-Session-ID"),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Remove item from cart"""
#     service = CartService(db)
    
#     user_id = uuid.UUID(current_user["id"]) if current_user else None
    
#     await service.remove_from_cart(
#         user_id=user_id,
#         session_id=session_id,
#         item_id=item_id
#     )

# @router.post(
#     "/save-for-later/{item_id}",
#     response_model=CartItemResponse,
#     summary="Save for later",
#     description="Move item to saved for later (Authenticated users only)"
# )
# async def save_for_later(
#     item_id: uuid.UUID,
#     current_user: dict = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Save item for later"""
#     service = CartService(db)
    
#     cart_item = await service.save_for_later(
#         user_id=uuid.UUID(current_user["id"]),
#         item_id=item_id
#     )
    
#     # Get full item details for response
#     await db.refresh(cart_item, ["product", "variant"])
    
#     return CartItemResponse(
#         id=cart_item.id,
#         product_id=cart_item.product_id,
#         variant_id=cart_item.variant_id,
#         quantity=cart_item.quantity,
#         price=cart_item.price,
#         saved_for_later=cart_item.saved_for_later,
#         created_at=cart_item.created_at,
#         product_title=cart_item.product.title,
#         product_slug=cart_item.product.slug,
#         product_thumbnail=cart_item.product.thumbnail,
#         product_price=cart_item.product.price,
#         product_final_price=cart_item.product.final_price,
#         product_stock=cart_item.product.stock,
#         variant_name=cart_item.variant.name if cart_item.variant else None,
#         subtotal=cart_item.price * cart_item.quantity,
#         is_available=cart_item.product.is_in_stock
#     )

# @router.post(
#     "/move-to-cart",
#     response_model=CartItemResponse,
#     summary="Move to cart",
#     description="Move item from saved to cart (Authenticated users only)"
# )
# async def move_to_cart(
#     request: MoveToCartRequest,
#     current_user: dict = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Move saved item to cart"""
#     service = CartService(db)
    
#     cart_item = await service.move_to_cart(
#         user_id=uuid.UUID(current_user["id"]),
#         item_id=request.item_id
#     )
    
#     # Get full item details for response
#     await db.refresh(cart_item, ["product", "variant"])
    
#     return CartItemResponse(
#         id=cart_item.id,
#         product_id=cart_item.product_id,
#         variant_id=cart_item.variant_id,
#         quantity=cart_item.quantity,
#         price=cart_item.price,
#         saved_for_later=cart_item.saved_for_later,
#         created_at=cart_item.created_at,
#         product_title=cart_item.product.title,
#         product_slug=cart_item.product.slug,
#         product_thumbnail=cart_item.product.thumbnail,
#         product_price=cart_item.product.price,
#         product_final_price=cart_item.product.final_price,
#         product_stock=cart_item.product.stock,
#         variant_name=cart_item.variant.name if cart_item.variant else None,
#         subtotal=cart_item.price * cart_item.quantity,
#         is_available=cart_item.product.is_in_stock
#     )

# @router.delete(
#     "/clear",
#     status_code=status.HTTP_204_NO_CONTENT,
#     summary="Clear cart",
#     description="Remove all items from cart"
# )
# async def clear_cart(
#     current_user: Optional[dict] = Depends(get_current_user_optional),
#     session_id: Optional[str] = Header(None, alias="X-Session-ID"),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Clear all cart items"""
#     service = CartService(db)
    
#     user_id = uuid.UUID(current_user["id"]) if current_user else None
    
#     await service.clear_cart(
#         user_id=user_id,
#         session_id=session_id
#     )

# @router.post(
#     "/merge",
#     status_code=status.HTTP_204_NO_CONTENT,
#     summary="Merge carts",
#     description="Merge session cart with user cart after login"
# )
# async def merge_carts(
#     request: CartMergeRequest,
#     current_user: dict = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Merge session cart with user cart"""
#     service = CartService(db)
    
#     await service.merge_carts(
#         user_id=uuid.UUID(current_user["id"]),
#         session_id=request.session_id
#     )

# @router.post(
#     "/apply-coupon",
#     response_model=dict,
#     summary="Apply coupon",
#     description="Apply coupon code to cart"
# )
# async def apply_coupon(
#     request: ApplyCouponRequest,
#     current_user: dict = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Apply coupon to cart"""
#     service = CartService(db)
    
#     result = await service.apply_coupon(
#         user_id=uuid.UUID(current_user["id"]),
#         coupon_code=request.coupon_code
#     )
    
#     return result
