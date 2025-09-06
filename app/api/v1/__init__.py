"""API v1 routes aggregation"""

from fastapi import APIRouter

from .auth.router import router as auth_router
from .products.router import router as products_router
from .categories.router import router as categories_router
from .orders.router import router as orders_router
from .cart.router import router as cart_router
from .payments.router import router as payments_router
from .notifications.router import router as notifications_router
from .admin.router import router as admin_router
from .chat.router import router as chat_router
from .inventory.router import router as inventory_router
from .rewards.router import router as rewards_router
from .sellers.router import router as sellers_router
from .users.router import router as users_router
from .analytics.router import router as analytics_router
from .cms.router import router as cms_router
from .coins.router import router as coins_router
from .coin_redemption import router as coin_redemption_router
from .referrals.router import router as referrals_router

# Create v1 router
api_router = APIRouter()

# Include all routers
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(products_router, prefix="/products", tags=["Products"])
api_router.include_router(categories_router, prefix="/categories", tags=["Categories"])
api_router.include_router(orders_router, prefix="/orders", tags=["Orders"])
api_router.include_router(cart_router, prefix="/cart", tags=["Cart"])
api_router.include_router(payments_router, prefix="/payments", tags=["Payments"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
api_router.include_router(chat_router, prefix="/chat", tags=["Chat"])
api_router.include_router(inventory_router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(rewards_router, prefix="/rewards", tags=["Rewards"])
api_router.include_router(sellers_router, prefix="/sellers", tags=["Sellers"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(cms_router, prefix="/cms", tags=["CMS"])
api_router.include_router(coins_router, prefix="/coins", tags=["Coins"])
api_router.include_router(coin_redemption_router, prefix="/coins", tags=["Coin Redemption"])
api_router.include_router(referrals_router, prefix="/referrals", tags=["Referrals"])

# Export router
router = api_router