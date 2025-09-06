"""Inventory schemas"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
import uuid

class StockMovement(BaseModel):
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID] = None
    quantity: int
    movement_type: str  # in, out, adjustment
    reason: str
    reference_id: Optional[str] = None
    notes: Optional[str] = None
    
class StockAlert(BaseModel):
    product_id: uuid.UUID
    current_stock: int
    reorder_level: int
    alert_type: str  # low_stock, out_of_stock, overstock
    
class InventoryReport(BaseModel):
    total_products: int
    total_value: Decimal
    low_stock_items: List[StockAlert]
    out_of_stock_items: List[StockAlert]
    stock_movements: List[StockMovement]
    
class BatchUpdate(BaseModel):
    updates: List[Dict[str, Any]]
    
class StockForecast(BaseModel):
    product_id: uuid.UUID
    current_stock: int
    average_daily_sales: float
    days_until_stockout: int
    recommended_reorder_quantity: int
    confidence_score: float
