"""Decorator for automatic audit logging"""

from functools import wraps
from typing import Callable, Optional, Dict, Any
from fastapi import Request
import inspect

from app.services.audit_service import AuditService

def audit_action(
    action: str,
    entity_type: str,
    entity_id_param: str = "id",
    description_template: Optional[str] = None
):
    """Decorator to automatically log admin actions"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find request and current_user in arguments
            request = None
            current_user = None
            entity_id = None
            
            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Extract needed values
            for param_name, param_value in bound_args.arguments.items():
                if isinstance(param_value, Request):
                    request = param_value
                elif param_name == "current_user" and isinstance(param_value, dict):
                    current_user = param_value
                elif param_name == entity_id_param:
                    entity_id = param_value
                    
            # Get db session
            db = bound_args.arguments.get("db")
            
            # Store old values if updating
            old_values = None
            if action in ["update", "delete"] and entity_id and db:
                # You might want to fetch the entity here to store old values
                pass
                
            # Execute the function
            result = await func(*args, **kwargs)
            
            # Log the action
            if current_user and db:
                audit_service = AuditService(db)
                
                # Build description
                description = description_template
                if description and entity_id:
                    description = description.format(entity_id=entity_id)
                    
                await audit_service.log_admin_action(
                    admin_id=current_user["id"],
                    action=action,
                    entity_type=entity_type,
                    entity_id=str(entity_id) if entity_id else "unknown",
                    description=description,
                    old_values=old_values,
                    new_values=kwargs if action == "create" else None,
                    request=request
                )
                
            return result
            
        return wrapper
    return decorator
