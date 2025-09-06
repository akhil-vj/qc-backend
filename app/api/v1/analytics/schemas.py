"""Analytics schemas"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from decimal import Decimal

class DateRangeFilter(BaseModel):
    start_date: date
    end_date: date

class SalesAnalytics(BaseModel):
    total_revenue: Decimal
    total_orders: int
    average_order_value: Decimal
    total_products_sold: int
    growth_percentage: float
    
class ProductPerformance(BaseModel):
    product_id: str
    product_name: str
    units_sold: int
    revenue: Decimal
    views: int
    conversion_rate: float
    
class CustomerAnalytics(BaseModel):
    total_customers: int
    new_customers: int
    returning_customers: int
    customer_lifetime_value: Decimal
    churn_rate: float
    
class SellerDashboardAnalytics(BaseModel):
    sales_analytics: SalesAnalytics
    top_products: List[ProductPerformance]
    customer_analytics: CustomerAnalytics
    revenue_by_date: List[Dict[str, Any]]
    orders_by_status: Dict[str, int]
    category_performance: List[Dict[str, Any]]
    
class UserBehaviorTracking(BaseModel):
    event_type: str  # view, click, add_to_cart, purchase, etc.
    user_id: Optional[str]
    session_id: str
    product_id: Optional[str]
    category_id: Optional[str]
    metadata: Dict[str, Any]
    timestamp: datetime
