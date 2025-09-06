"""Inventory management service"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
import numpy as np
from scipy import stats

from app.models import Product, ProductVariant, OrderItem, Order
from app.core.exceptions import BadRequestException
from app.services.notification import NotificationService
from .schemas import StockMovement, StockAlert, InventoryReport, StockForecast

class InventoryService:
    """Advanced inventory management service"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_service = NotificationService(db)
        
    async def record_stock_movement(
        self,
        movement: StockMovement,
        user_id: str
    ) -> None:
        """Record stock movement with audit trail"""
        # Get product
        product = await self.db.get(Product, movement.product_id)
        if not product:
            raise BadRequestException("Product not found")
            
        # Calculate new stock
        if movement.movement_type == "in":
            new_stock = product.stock + movement.quantity
        elif movement.movement_type == "out":
            new_stock = product.stock - movement.quantity
        else:  # adjustment
            new_stock = movement.quantity
            
        if new_stock < 0:
            raise BadRequestException("Insufficient stock")
            
        # Update stock
        old_stock = product.stock
        product.stock = new_stock
        
        # Note: InventoryLog creation removed for now - can be implemented when model is available
        
        self.db.add(product)
        await self.db.commit()
        
        # Check for alerts
        await self._check_stock_alerts(product)
        
    async def get_inventory_report(
        self,
        seller_id: str,
        include_movements: bool = True
    ) -> InventoryReport:
        """Get comprehensive inventory report"""
        # Get all products
        products = await self.db.execute(
            select(Product).where(Product.seller_id == seller_id)
        )
        products = products.scalars().all()
        
        total_value = Decimal("0")
        low_stock = []
        out_of_stock = []
        
        for product in products:
            # Calculate inventory value
            total_value += product.stock * product.price
            
            # Check stock levels
            reorder_level = await self._calculate_reorder_level(product.id)
            
            if product.stock == 0:
                out_of_stock.append(StockAlert(
                    product_id=product.id,
                    current_stock=0,
                    reorder_level=reorder_level,
                    alert_type="out_of_stock"
                ))
            elif product.stock < reorder_level:
                low_stock.append(StockAlert(
                    product_id=product.id,
                    current_stock=product.stock,
                    reorder_level=reorder_level,
                    alert_type="low_stock"
                ))
                
        # Get recent movements - simplified for now without InventoryLog
        movements = []
        if include_movements:
            # Note: This section will be implemented when InventoryLog model is available
            pass
                
        return InventoryReport(
            total_products=len(products),
            total_value=total_value,
            low_stock_items=low_stock,
            out_of_stock_items=out_of_stock,
            stock_movements=movements
        )
        
    async def batch_update_stock(
        self,
        updates: List[Dict[str, Any]],
        user_id: str
    ) -> Dict[str, Any]:
        """Batch update product stock"""
        success_count = 0
        errors = []
        
        for update in updates:
            try:
                movement = StockMovement(**update)
                await self.record_stock_movement(movement, user_id)
                success_count += 1
            except Exception as e:
                errors.append({
                    "product_id": update.get("product_id"),
                    "error": str(e)
                })
                
        return {
            "success_count": success_count,
            "error_count": len(errors),
            "errors": errors
        }
        
    async def get_stock_forecast(
        self,
        product_id: uuid.UUID,
        days: int = 30
    ) -> StockForecast:
        """Predict stock requirements using ML"""
        # Get historical sales data
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)
        
        sales_data = await self.db.execute(
            select(
                func.date(Order.created_at).label("date"),
                func.sum(OrderItem.quantity).label("quantity")
            )
            .join(Order)
            .where(
                and_(
                    OrderItem.product_id == product_id,
                    Order.status == "delivered",
                    Order.created_at >= start_date
                )
            )
            .group_by(func.date(Order.created_at))
        )
        
        # Convert to numpy array
        daily_sales = []
        for row in sales_data:
            daily_sales.append(row.quantity or 0)
            
        if not daily_sales:
            daily_sales = [0]
            
        # Calculate statistics
        avg_daily_sales = np.mean(daily_sales)
        std_daily_sales = np.std(daily_sales)
        
        # Get current stock
        product = await self.db.get(Product, product_id)
        current_stock = product.stock
        
        # Calculate days until stockout
        if avg_daily_sales > 0:
            days_until_stockout = int(current_stock / avg_daily_sales)
        else:
            days_until_stockout = 999
            
        # Calculate recommended reorder quantity
        # Using (avg + 2*std) * lead_time + safety_stock
        lead_time = 7  # days
        service_level = 0.95
        z_score = stats.norm.ppf(service_level)
        
        safety_stock = z_score * std_daily_sales * np.sqrt(lead_time)
        reorder_quantity = int(
            (avg_daily_sales * lead_time) + safety_stock
        )
        
        # Calculate confidence score based on data availability
        confidence = min(len(daily_sales) / 30, 1.0)
        
        return StockForecast(
            product_id=product_id,
            current_stock=current_stock,
            average_daily_sales=avg_daily_sales,
            days_until_stockout=days_until_stockout,
            recommended_reorder_quantity=reorder_quantity,
            confidence_score=confidence
        )
        
    async def _calculate_reorder_level(self, product_id: uuid.UUID) -> int:
        """Calculate dynamic reorder level"""
        forecast = await self.get_stock_forecast(product_id)
        
        # Reorder when we have 2 weeks of stock left
        return int(forecast.average_daily_sales * 14)
        
    async def _check_stock_alerts(self, product: Product) -> None:
        """Check and send stock alerts"""
        reorder_level = await self._calculate_reorder_level(product.id)
        
        if product.stock == 0:
            await self.notification_service.send_stock_alert(
                product.seller_id,
                product.id,
                "out_of_stock"
            )
        elif product.stock < reorder_level:
            await self.notification_service.send_stock_alert(
                product.seller_id,
                product.id,
                "low_stock"
            )
