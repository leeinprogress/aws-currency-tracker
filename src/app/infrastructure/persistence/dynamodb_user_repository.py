from datetime import datetime, UTC
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key

from app.core.config import settings
from app.domain.entities.user import User
from app.domain.repositories import IUserRepository
from app.infrastructure.persistence.mappers import UserMapper


class DynamoDBUserRepository(IUserRepository):
    def __init__(self, table_name: Optional[str] = None):
        resource = boto3.resource("dynamodb")
        self.table = resource.Table(table_name or settings.USERS_TABLE_NAME)
        self.mapper = UserMapper()

    async def save(self, user: User) -> User:
        item = self.mapper.to_dynamodb(user)

        if not user.created_at:
            item["created_at"] = datetime.now(UTC).isoformat()
        if not user.updated_at:
            item["updated_at"] = datetime.now(UTC).isoformat()

        self.table.put_item(Item=item)
        return user

    async def find_by_id(self, user_id: str) -> Optional[User]:
        response = self.table.get_item(Key={"user_id": user_id})
        item = response.get("Item")
        return self.mapper.to_entity(item) if item else None

    async def find_by_email(self, email: str) -> Optional[User]:
        try:
            response = self.table.query(
                IndexName="email-index",
                KeyConditionExpression=Key("email").eq(email),
            )
            items = response.get("Items", [])
            if not items:
                return None
            return self.mapper.to_entity(items[0])
        except Exception:
            response = self.table.scan(FilterExpression=Attr("email").eq(email))
            items = response.get("Items", [])
            if not items:
                return None
            return self.mapper.to_entity(items[0])

    async def find_by_google_id(self, google_id: str) -> Optional[User]:
        try:
            response = self.table.query(
                IndexName="google-index",
                KeyConditionExpression=Key("google_id").eq(google_id),
            )
            items = response.get("Items", [])
            if not items:
                return None
            return self.mapper.to_entity(items[0])
        except Exception:
            response = self.table.scan(FilterExpression=Attr("google_id").eq(google_id))
            items = response.get("Items", [])
            if not items:
                return None
            return self.mapper.to_entity(items[0])

    async def update(self, user_id: str, **kwargs: Any) -> Optional[User]:
        if not kwargs:
            return await self.find_by_id(user_id)

        now = datetime.now(UTC).isoformat()
        kwargs["updated_at"] = now

        update_parts = []
        remove_parts = []
        expression_attr_names: dict[str, str] = {}
        expression_attr_values: dict[str, Any] = {}

        for key, value in kwargs.items():
            safe_key = f"#attr_{key}"
            expression_attr_names[safe_key] = key
            if value is None:
                remove_parts.append(safe_key)
            else:
                val_key = f":val_{key}"
                update_parts.append(f"{safe_key} = {val_key}")
                expression_attr_values[val_key] = value

        expression = ""
        if update_parts:
            expression += "SET " + ", ".join(update_parts)
        if remove_parts:
            expression += (" " if expression else "") + "REMOVE " + ", ".join(remove_parts)

        update_kwargs: dict[str, Any] = {
            "Key": {"user_id": user_id},
            "UpdateExpression": expression,
            "ExpressionAttributeNames": expression_attr_names,
        }
        if expression_attr_values:
            update_kwargs["ExpressionAttributeValues"] = expression_attr_values

        self.table.update_item(**update_kwargs)
        return await self.find_by_id(user_id)

    async def delete(self, user_id: str) -> bool:
        self.table.delete_item(Key={"user_id": user_id})
        return True


__all__ = ["DynamoDBUserRepository"]
