"""
Invoice service for handling invoice generation and management
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderStatus
from app.models.user import User
from app.models.product import Product
from app.core.config import settings


class InvoiceService:
    """
    Service for managing invoices and billing
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def generate_invoice(
        self, 
        order_id: int, 
        user_id: int
    ) -> Dict[str, Any]:
        """
        Generate an invoice for an order
        """
        try:
            # Get order with all related data
            result = await self.db.execute(
                select(Order)
                .options(
                    selectinload(Order.items),
                    selectinload(Order.user),
                    selectinload(Order.payment)
                )
                .where(
                    and_(
                        Order.id == order_id,
                        Order.user_id == user_id
                    )
                )
            )
            order = result.scalar_one_or_none()
            
            if not order:
                return {"success": False, "error": "Order not found"}
            
            # Calculate invoice details
            invoice_data = {
                "invoice_number": f"INV-{order.id}-{datetime.now().strftime('%Y%m%d')}",
                "order_id": order.id,
                "customer": {
                    "name": f"{order.user.first_name} {order.user.last_name}",
                    "email": order.user.email,
                    "phone": getattr(order.user, 'phone', None)
                },
                "order_date": order.created_at.isoformat(),
                "due_date": (order.created_at + timedelta(days=30)).isoformat(),
                "items": [],
                "subtotal": float(order.subtotal),
                "tax_amount": float(order.tax_amount),
                "shipping_cost": float(order.shipping_cost),
                "discount_amount": float(order.discount_amount),
                "total_amount": float(order.total_amount),
                "status": order.status.value,
                "payment_status": order.payment.status.value if order.payment else "pending"
            }
            
            # Add order items
            for item in order.items:
                invoice_data["items"].append({
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price),
                    "total_price": float(item.total_price)
                })
            
            return {
                "success": True,
                "invoice": invoice_data
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to generate invoice: {str(e)}"
            }
    
    async def get_invoice_by_order(
        self, 
        order_id: int, 
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get invoice data for a specific order
        """
        result = await self.generate_invoice(order_id, user_id)
        return result.get("invoice") if result.get("success") else None
    
    async def get_user_invoices(
        self, 
        user_id: int, 
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all invoices for a user
        """
        try:
            result = await self.db.execute(
                select(Order)
                .options(
                    selectinload(Order.items),
                    selectinload(Order.payment)
                )
                .where(Order.user_id == user_id)
                .order_by(Order.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            orders = result.scalars().all()
            
            invoices = []
            for order in orders:
                invoice_result = await self.generate_invoice(order.id, user_id)
                if invoice_result.get("success"):
                    invoices.append(invoice_result["invoice"])
            
            return invoices
            
        except Exception:
            return []
    
    async def mark_invoice_paid(
        self, 
        order_id: int, 
        payment_date: Optional[datetime] = None
    ) -> bool:
        """
        Mark an invoice as paid
        """
        try:
            if payment_date is None:
                payment_date = datetime.utcnow()
            
            # This would typically update an invoice table
            # For now, we'll just verify the order exists
            result = await self.db.execute(
                select(Order).where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()
            
            return order is not None
            
        except Exception:
            return False
    
    async def get_invoice_summary(
        self, 
        user_id: int, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get invoice summary for a user within a date range
        """
        try:
            query = select(Order).where(Order.user_id == user_id)
            
            if start_date:
                query = query.where(Order.created_at >= start_date)
            if end_date:
                query = query.where(Order.created_at <= end_date)
            
            result = await self.db.execute(query)
            orders = result.scalars().all()
            
            total_amount = sum(float(order.total_amount) for order in orders)
            paid_orders = [o for o in orders if o.status == OrderStatus.DELIVERED]
            pending_orders = [o for o in orders if o.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]]
            
            return {
                "total_invoices": len(orders),
                "total_amount": total_amount,
                "paid_invoices": len(paid_orders),
                "paid_amount": sum(float(o.total_amount) for o in paid_orders),
                "pending_invoices": len(pending_orders),
                "pending_amount": sum(float(o.total_amount) for o in pending_orders)
            }
            
        except Exception:
            return {
                "total_invoices": 0,
                "total_amount": 0.0,
                "paid_invoices": 0,
                "paid_amount": 0.0,
                "pending_invoices": 0,
                "pending_amount": 0.0
            }
