"""Models package initialization"""

from .base import Base, register_model
from .user import User, UserProfile, UserRole
from .product import Product, ProductVariant, ProductImage
from .order import Order, OrderItem, OrderStatus, PaymentStatus, OrderStatusHistory
from .category import Category
from .brand import Brand
from .cart import CartItem
from .review import Review
from .address import Address
from .price_history import PriceHistory
from .reward import Reward, RewardTransaction
from .payment import Payment, PaymentMethod
from .notification import Notification
from .coupon import Coupon, CouponUsage
from .wishlist import WishlistItem
from .seller import SellerProfile, SellerPayout
from .flash_sale import FlashSale, FlashSaleProduct
from .referral import ReferralTracking
from .coin_transaction import CoinTransaction, CoinRedemption
from .push_notification import DeviceToken, PushNotificationLog
from .notifications import NotificationLog

# Register all models
register_model(User)
register_model(UserProfile)
register_model(Product)
register_model(ProductVariant)
register_model(ProductImage)
register_model(Order)
register_model(OrderItem)
register_model(OrderStatusHistory)
register_model(Category)
register_model(Brand)
register_model(CartItem)
register_model(Review)
register_model(Address)
register_model(PriceHistory)
register_model(Reward)
register_model(RewardTransaction)
register_model(Payment)
register_model(Notification)
register_model(Coupon)
register_model(CouponUsage)
register_model(WishlistItem)
register_model(SellerProfile)
register_model(SellerPayout)
register_model(FlashSale)
register_model(FlashSaleProduct)
register_model(ReferralTracking)
register_model(CoinTransaction)
register_model(CoinRedemption)
register_model(DeviceToken)
register_model(PushNotificationLog)
register_model(NotificationLog)

# Export all models
__all__ = [
    "Base",
    "User",
    "UserProfile",
    "UserRole",
    "Product",
    "ProductVariant",
    "ProductImage",
    "Order",
    "OrderItem",
    "OrderStatus",
    "PaymentStatus",
    "OrderStatusHistory",
    "Category",
    "Brand",
    "CartItem",
    "Review",
    "Address",
    "PriceHistory",
    "Reward",
    "RewardTransaction",
    "Payment",
    "PaymentMethod",
    "Notification",
    "Coupon",
    "CouponUsage",
    "WishlistItem",
    "SellerProfile",
    "SellerPayout",
    "FlashSale",
    "FlashSaleProduct",
    "ReferralTracking",
    "CoinTransaction",
    "CoinRedemption",
    "DeviceToken",
    "PushNotificationLog",
    "NotificationLog",
]