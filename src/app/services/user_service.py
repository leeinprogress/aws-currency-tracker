"""
User service layer - business logic
"""
import uuid
from typing import Optional

from app.db.repositories import UserRepository
from app.core.security import verify_password, get_password_hash
from app.db.models.user import User
from app.schemas.user import UserCreate


class UserService:
    """User business logic service"""

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        # Check if user already exists
        existing_user = await self.user_repository.get_user_by_email(user_data.email)
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Create user
        user = User(
            user_id=str(uuid.uuid4()),
            email=user_data.email,
            telegram_chat_id=user_data.telegram_chat_id,
            hashed_password=get_password_hash(user_data.password),
            is_active=True,
        )
        return await self.user_repository.create_user(user)
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user"""
        user = await self.user_repository.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        return await self.user_repository.get_user_by_id(user_id)

