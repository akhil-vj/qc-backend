"""
Order state machine for managing order status transitions
"""

from typing import Dict, List, Set
from app.models.order import OrderStatus

class OrderStateMachine:
    """
    Manages valid order status transitions
    """
    
    def __init__(self):
        # Define valid transitions
        self.transitions: Dict[OrderStatus, Set[OrderStatus]] = {
            OrderStatus.PENDING: {
                OrderStatus.CONFIRMED,
                OrderStatus.CANCELLED
            },
            OrderStatus.CONFIRMED: {
                OrderStatus.PROCESSING,
                OrderStatus.CANCELLED
            },
            OrderStatus.PROCESSING: {
                OrderStatus.SHIPPED,
                OrderStatus.CANCELLED
            },
            OrderStatus.SHIPPED: {
                OrderStatus.OUT_FOR_DELIVERY,
                OrderStatus.DELIVERED,
                OrderStatus.CANCELLED
            },
            OrderStatus.OUT_FOR_DELIVERY: {
                OrderStatus.DELIVERED,
                OrderStatus.FAILED
            },
            OrderStatus.DELIVERED: {
                OrderStatus.REFUNDED  # For returns
            },
            OrderStatus.CANCELLED: {
                OrderStatus.REFUNDED  # If payment was made
            },
            OrderStatus.FAILED: {
                OrderStatus.CANCELLED,
                OrderStatus.PROCESSING  # For retry
            },
            OrderStatus.REFUNDED: set()  # Terminal state
        }
    
    def can_transition(
        self,
        current_status: OrderStatus,
        new_status: OrderStatus
    ) -> bool:
        """
        Check if transition is valid
        
        Args:
            current_status: Current order status
            new_status: Desired new status
            
        Returns:
            True if transition is allowed
        """
        valid_transitions = self.transitions.get(current_status, set())
        return new_status in valid_transitions
    
    def get_valid_transitions(
        self,
        current_status: OrderStatus
    ) -> List[OrderStatus]:
        """
        Get list of valid transitions from current status
        
        Args:
            current_status: Current order status
            
        Returns:
            List of valid next statuses
        """
        return list(self.transitions.get(current_status, set()))
    
    def is_terminal_state(self, status: OrderStatus) -> bool:
        """
        Check if status is a terminal state
        
        Args:
            status: Order status
            
        Returns:
            True if no more transitions possible
        """
        return len(self.transitions.get(status, set())) == 0
    
    def is_cancellable(self, status: OrderStatus) -> bool:
        """
        Check if order can be cancelled in current status
        
        Args:
            status: Current order status
            
        Returns:
            True if order can be cancelled
        """
        return OrderStatus.CANCELLED in self.transitions.get(status, set())
    
    def is_refundable(self, status: OrderStatus) -> bool:
        """
        Check if order can be refunded in current status
        
        Args:
            status: Current order status
            
        Returns:
            True if order can be refunded
        """
        return status in [OrderStatus.CANCELLED, OrderStatus.DELIVERED]
