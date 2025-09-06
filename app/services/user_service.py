"""User service for user management operations"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserProfile
from app.core.security import SecurityUtils


class UserService:
    """Service class for user operations"""
    
    @staticmethod
    async def get_users(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[User]:
        """Get users with filtering and pagination"""
        query = db.query(User)
        
        if search:
            query = query.filter(
                or_(
                    User.email.ilike(f"%{search}%"),
                    User.first_name.ilike(f"%{search}%"),
                    User.last_name.ilike(f"%{search}%")
                )
            )
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    async def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    async def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    async def create_user(db: Session, user_data: UserCreate) -> User:
        """Create a new user"""
        hashed_password = SecurityUtils.hash_password(user_data.password)
        
        db_user = User(
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            hashed_password=hashed_password,
            is_active=user_data.is_active
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    
    @staticmethod
    async def update_user(db: Session, user_id: int, user_update: UserUpdate) -> Optional[User]:
        """Update user information"""
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            return None
        
        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        db.commit()
        db.refresh(db_user)
        return db_user
    
    @staticmethod
    async def delete_user(db: Session, user_id: int) -> bool:
        """Soft delete a user"""
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            return False
        
        db_user.is_active = False
        db.commit()
        return True
    
    @staticmethod
    async def activate_user(db: Session, user_id: int) -> bool:
        """Activate a user account"""
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            return False
        
        db_user.is_active = True
        db.commit()
        return True
    
    @staticmethod
    async def deactivate_user(db: Session, user_id: int) -> bool:
        """Deactivate a user account"""
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            return False
        
        db_user.is_active = False
        db.commit()
        return True
    
    @staticmethod
    async def get_user_profile(db: Session, user_id: int) -> Optional[dict]:
        """Get user profile information"""
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            return None
        
        return {
            "id": db_user.id,
            "email": db_user.email,
            "first_name": db_user.first_name,
            "last_name": db_user.last_name,
            "phone": db_user.phone,
            "is_active": db_user.is_active,
            "created_at": db_user.created_at,
            "last_login": getattr(db_user, 'last_login', None)
        }
    
    @staticmethod
    async def get_user_addresses(db: Session, user_id: int) -> List[dict]:
        """Get user addresses"""
        # Mock implementation - would fetch from UserAddress model
        return [
            {
                "id": 1,
                "title": "Home",
                "address_line_1": "123 Main St",
                "city": "New York",
                "state": "NY",
                "postal_code": "10001",
                "country": "United States",
                "is_default": True
            }
        ]
