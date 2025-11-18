"""
User repository backed by DynamoDB
"""
from __future__ import annotations

from datetime import datetime, UTC
from typing import Optional, Protocol, runtime_checkable

import boto3
from boto3.dynamodb.conditions import Attr, Key

from app.core.config import settings
from app.db.models.user import User


@runtime_checkable
class UserRepository(Protocol):
    """User repository contract"""

    async def create_user(self, user: User) -> User:
        ...

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        ...

    async def get_user_by_email(self, email: str) -> Optional[User]:
        ...

    async def update_user(self, user_id: str, **kwargs) -> Optional[User]:
        ...


class DynamoDBUserRepository(UserRepository):
    """Concrete DynamoDB implementation for users"""

    def __init__(self, table_name: Optional[str] = None):
        resource = boto3.resource("dynamodb")
        self.table = resource.Table(table_name or settings.USERS_TABLE_NAME)

    async def create_user(self, user: User) -> User:
        item = user.to_dict(exclude_password=False)
        item["created_at"] = datetime.now(UTC).isoformat()
        item["updated_at"] = datetime.now(UTC).isoformat()
        self.table.put_item(Item=item)
        return user

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        response = self.table.get_item(Key={"user_id": user_id})
        item = response.get("Item")
        return User.from_dict(item) if item else None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        try:
            response = self.table.query(
                IndexName="email-index",
                KeyConditionExpression=Key("email").eq(email),
            )
            items = response.get("Items", [])
            if not items:
                return None
            return User.from_dict(items[0])
        except Exception:
            response = self.table.scan(FilterExpression=Attr("email").eq(email))
            items = response.get("Items", [])
            if not items:
                return None
            return User.from_dict(items[0])

    async def update_user(self, user_id: str, **kwargs) -> Optional[User]:
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}

        for key, value in kwargs.items():
            if value is not None:
                update_expression_parts.append(f"#{key} = :{key}")
                expression_attribute_names[f"#{key}"] = key
                expression_attribute_values[f":{key}"] = value

        if not update_expression_parts:
            return await self.get_user_by_id(user_id)

        update_expression_parts.append("#updated_at = :updated_at")
        expression_attribute_names["#updated_at"] = "updated_at"
        expression_attribute_values[":updated_at"] = datetime.utcnow().isoformat()

        update_expression = "SET " + ", ".join(update_expression_parts)

        try:
            self.table.update_item(
                Key={"user_id": user_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
            )
            return await self.get_user_by_id(user_id)
        except Exception:
            return None


__all__ = ["UserRepository", "DynamoDBUserRepository"]

