"""
Alert repository backed by DynamoDB
"""
from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
from typing import List, Optional, Protocol, runtime_checkable

import boto3
from boto3.dynamodb.conditions import Attr, Key

from app.core.config import settings
from app.db.models.alert import Alert


@runtime_checkable
class AlertRepository(Protocol):
    """Alert repository contract"""

    async def create_alert(self, alert: Alert) -> Alert:
        ...

    async def get_alert(self, alert_id: str) -> Optional[Alert]:
        ...

    async def list_alerts(
        self,
        user_id: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[Alert]:
        ...

    async def update_alert(self, alert_id: str, **kwargs) -> Optional[Alert]:
        ...

    async def delete_alert(self, alert_id: str) -> bool:
        ...

    async def get_active_alerts_by_base_currency(self, base_currency: str) -> List[Alert]:
        ...


class DynamoDBAlertRepository(AlertRepository):
    """Concrete DynamoDB implementation for alerts"""

    def __init__(self, table_name: Optional[str] = None):
        resource = boto3.resource("dynamodb")
        self.table = resource.Table(table_name or settings.ALERTS_TABLE_NAME)

    async def create_alert(self, alert: Alert) -> Alert:
        item = alert.to_dict()
        item["created_at"] = datetime.now(UTC).isoformat()
        item["updated_at"] = datetime.now(UTC).isoformat()
        self.table.put_item(Item=item)
        return alert

    async def get_alert(self, alert_id: str) -> Optional[Alert]:
        response = self.table.get_item(Key={"alert_id": alert_id})
        item = response.get("Item")
        return Alert.from_dict(item) if item else None

    async def list_alerts(
        self,
        user_id: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[Alert]:
        if user_id:
            try:
                key_condition = Key("user_id").eq(user_id)
                if is_active is not None:
                    response = self.table.query(
                        IndexName="user_id-index",
                        KeyConditionExpression=key_condition,
                        FilterExpression=Attr("is_active").eq(is_active),
                    )
                else:
                    response = self.table.query(
                        IndexName="user_id-index",
                        KeyConditionExpression=key_condition,
                    )
                return [Alert.from_dict(item) for item in response.get("Items", [])]
            except Exception:
                # GSI not ready – fall back to scan below
                pass

        filter_expression = Attr("is_active").eq(is_active) if is_active is not None else None
        if filter_expression:
            response = self.table.scan(FilterExpression=filter_expression)
        else:
            response = self.table.scan()
        return [Alert.from_dict(item) for item in response.get("Items", [])]

    async def update_alert(self, alert_id: str, **kwargs) -> Optional[Alert]:
        update_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}

        for key, value in kwargs.items():
            if value is not None:
                update_expression_parts.append(f"#{key} = :{key}")
                expression_attribute_names[f"#{key}"] = key
                # Convert float to Decimal for DynamoDB compatibility
                if isinstance(value, float):
                    expression_attribute_values[f":{key}"] = Decimal(str(value))
                else:
                    expression_attribute_values[f":{key}"] = value

        if not update_expression_parts:
            return await self.get_alert(alert_id)

        update_expression_parts.append("#updated_at = :updated_at")
        expression_attribute_names["#updated_at"] = "updated_at"
        expression_attribute_values[":updated_at"] = datetime.now(UTC).isoformat()

        update_expression = "SET " + ", ".join(update_expression_parts)
        try:
            self.table.update_item(
                Key={"alert_id": alert_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW",
            )
            return await self.get_alert(alert_id)
        except Exception:
            return None

    async def delete_alert(self, alert_id: str) -> bool:
        try:
            self.table.delete_item(Key={"alert_id": alert_id})
            return True
        except Exception:
            return False

    async def get_active_alerts_by_base_currency(self, base_currency: str) -> List[Alert]:
        try:
            response = self.table.query(
                IndexName="base_currency-index",
                KeyConditionExpression=Key("base_currency").eq(base_currency),
                FilterExpression=Attr("is_active").eq(True),
            )
            return [Alert.from_dict(item) for item in response.get("Items", [])]
        except Exception:
            response = self.table.scan(
                FilterExpression=Attr("base_currency").eq(base_currency) & Attr("is_active").eq(True)
            )
            return [Alert.from_dict(item) for item in response.get("Items", [])]


__all__ = ["AlertRepository", "DynamoDBAlertRepository"]

