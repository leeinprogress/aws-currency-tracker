import uuid
from typing import Optional

from app.core.exceptions import UserNotFoundError
from app.core.security import get_password_hash, hash_password, verify_password
from app.domain.entities.user import User
from app.domain.repositories import IAlertRepository, IUserRepository
from app.infrastructure.logging.logger import get_logger
from app.schemas.user import UserCreate

logger = get_logger(__name__)


class UserService:
    def __init__(
        self,
        user_repository: IUserRepository,
        alert_repository: Optional[IAlertRepository] = None,
    ):
        self.user_repository = user_repository
        self.alert_repository = alert_repository

    async def create_user(self, user_data: UserCreate) -> User:
        logger.info("creating_user", email=user_data.email)

        existing_user = await self.user_repository.find_by_email(user_data.email)
        if existing_user:
            logger.warning("user_creation_failed", email=user_data.email, reason="email_exists")
            raise ValueError("User with this email already exists")

        user = User(
            user_id=str(uuid.uuid4()),
            email=user_data.email,
            telegram_chat_id=user_data.telegram_chat_id,
            hashed_password=get_password_hash(user_data.password),
            is_active=True,
            auth_provider="local",
        )
        created_user = await self.user_repository.save(user)

        logger.info("user_created", user_id=created_user.user_id, email=created_user.email)
        return created_user

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        logger.info("authentication_attempt", email=email)

        user = await self.user_repository.find_by_email(email)
        if not user:
            logger.warning("authentication_failed", email=email, reason="user_not_found")
            return None
        if not user.hashed_password or not verify_password(password, user.hashed_password):
            logger.warning(
                "authentication_failed", email=email, user_id=user.user_id, reason="invalid_password"
            )
            return None
        if not user.is_active:
            logger.warning(
                "authentication_failed", email=email, user_id=user.user_id, reason="user_inactive"
            )
            return None

        logger.info("authentication_successful", user_id=user.user_id, email=email)
        return user

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        return await self.user_repository.find_by_id(user_id)

    async def set_refresh_token(self, user_id: str, refresh_token: str) -> None:
        token_hash = hash_password(refresh_token)
        await self.user_repository.update(user_id, refresh_token_hash=token_hash)

    async def clear_refresh_token(self, user_id: str) -> None:
        await self.user_repository.update(user_id, refresh_token_hash=None)

    async def verify_refresh_token(self, user_id: str, refresh_token: str) -> bool:
        user = await self.user_repository.find_by_id(user_id)
        if not user or not user.refresh_token_hash:
            return False
        return verify_password(refresh_token, user.refresh_token_hash)

    async def get_or_create_google_user(
        self,
        email: str,
        google_id: str,
        name: Optional[str] = None,
    ) -> User:
        user = await self.user_repository.find_by_google_id(google_id)
        if user:
            return user

        # Check if local account exists with same email — link accounts
        user = await self.user_repository.find_by_email(email)
        if user:
            updated = await self.user_repository.update(
                user.user_id,
                google_id=google_id,
                auth_provider="google",
            )
            return updated or user

        new_user = User(
            user_id=str(uuid.uuid4()),
            email=email,
            is_active=True,
            auth_provider="google",
            google_id=google_id,
        )
        return await self.user_repository.save(new_user)

    async def update_user(self, user_id: str, **kwargs: object) -> User:
        user = await self.user_repository.find_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")
        updated = await self.user_repository.update(user_id, **kwargs)
        if not updated:
            raise UserNotFoundError(f"User {user_id} not found after update")
        return updated

    async def delete_user(self, user_id: str) -> None:
        """Delete user record, all their alerts, and clear refresh token hash."""
        user = await self.user_repository.find_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        # Delete all alerts for this user
        if self.alert_repository:
            alerts = await self.alert_repository.find_by_user(user_id)
            for alert in alerts:
                await self.alert_repository.delete(alert.alert_id)
            logger.info("user_alerts_deleted", user_id=user_id, count=len(alerts))

        await self.user_repository.delete(user_id)
        logger.info("user_deleted", user_id=user_id)

    async def count_alerts(self, user_id: str) -> int:
        if not self.alert_repository:
            return 0
        alerts = await self.alert_repository.find_by_user(user_id)
        return len(alerts)
