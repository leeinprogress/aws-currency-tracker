from datetime import datetime, UTC
from decimal import Decimal
from typing import List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.core.config import settings
from app.domain.entities.alert import Alert
from app.domain.repositories import IAlertRepository
from app.infrastructure.persistence.mappers import AlertMapper
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class DuplicateAlertError(Exception):
    """Raised when attempting to create a duplicate alert."""
    pass


class DynamoDBAlertRepository(IAlertRepository):
    def __init__(self, table_name: Optional[str] = None):
        resource = boto3.resource("dynamodb")
        self.table = resource.Table(table_name or settings.ALERTS_TABLE_NAME)
        self.mapper = AlertMapper()

    async def save(self, alert: Alert, check_duplicate: bool = True) -> Alert:
        """
        Save an alert with conditional check to prevent duplicates.

        Args:
            alert: Alert entity to save
            check_duplicate: If True, prevents saving if alert_id already exists

        Raises:
            DuplicateAlertError: If alert_id already exists and check_duplicate is True
        """
        item = self.mapper.to_dynamodb(alert)

        if not alert.created_at:
            item["created_at"] = datetime.now(UTC).isoformat()
        if not alert.updated_at:
            item["updated_at"] = datetime.now(UTC).isoformat()

        try:
            if check_duplicate:
                # Conditional put - only succeeds if alert_id doesn't exist
                self.table.put_item(
                    Item=item,
                    ConditionExpression=Attr("alert_id").not_exists(),
                )
            else:
                self.table.put_item(Item=item)

            logger.info("alert_saved", alert_id=alert.alert_id, user_id=alert.user_id)
            return alert

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning("duplicate_alert_rejected", alert_id=alert.alert_id)
                raise DuplicateAlertError(f"Alert with id {alert.alert_id} already exists")
            raise
    
    async def find_by_id(self, alert_id: str) -> Optional[Alert]:
        response = self.table.get_item(Key={"alert_id": alert_id})
        item = response.get("Item")
        return self.mapper.to_entity(item) if item else None
    
    async def find_by_user(self, user_id: str, is_active: Optional[bool] = None) -> List[Alert]:
        """
        Find alerts for a user, optionally filtered by active status.

        Uses sparse GSI (active_user_id-index) for active alerts queries,
        which only indexes active items - more efficient than filtering.
        """
        try:
            if is_active is True:
                # Use sparse GSI - only contains active alerts
                response = self.table.query(
                    IndexName="active_user_id-index",
                    KeyConditionExpression=Key("active_user_id").eq(user_id),
                )
            elif is_active is False:
                # Query all user alerts, filter for inactive
                response = self.table.query(
                    IndexName="user_id-index",
                    KeyConditionExpression=Key("user_id").eq(user_id),
                    FilterExpression=Attr("is_active").eq(False),
                )
            else:
                # No filter - get all alerts for user
                response = self.table.query(
                    IndexName="user_id-index",
                    KeyConditionExpression=Key("user_id").eq(user_id),
                )
            return [self.mapper.to_entity(item) for item in response.get("Items", [])]

        except ClientError as e:
            logger.error("find_by_user_error", user_id=user_id, error=str(e))
            # Fallback to scan if GSI query fails
            filter_expression = Attr("user_id").eq(user_id)
            if is_active is not None:
                filter_expression = filter_expression & Attr("is_active").eq(is_active)
            response = self.table.scan(FilterExpression=filter_expression)
            return [self.mapper.to_entity(item) for item in response.get("Items", [])]
    
    async def find_all_active(self) -> List[Alert]:
        response = self.table.scan(FilterExpression=Attr("is_active").eq(True))
        return [self.mapper.to_entity(item) for item in response.get("Items", [])]
    
    async def delete(self, alert_id: str) -> bool:
        try:
            self.table.delete_item(Key={"alert_id": alert_id})
            return True
        except Exception:
            return False
    
    async def update(self, alert_id: str, **kwargs) -> Optional[Alert]:
        update_expression_parts = []
        remove_expression_parts = []
        expression_attribute_values = {}
        expression_attribute_names = {}

        is_active_changing = "is_active" in kwargs
        new_is_active = kwargs.get("is_active")

        for key, value in kwargs.items():
            if value is not None:
                update_expression_parts.append(f"#{key} = :{key}")
                expression_attribute_names[f"#{key}"] = key
                if isinstance(value, float):
                    expression_attribute_values[f":{key}"] = Decimal(str(value))
                else:
                    expression_attribute_values[f":{key}"] = value

        if not update_expression_parts:
            return await self.find_by_id(alert_id)

        if is_active_changing:
            if new_is_active:
                current_alert = await self.find_by_id(alert_id)
                if current_alert:
                    update_expression_parts.append("#active_user_id = :active_user_id")
                    expression_attribute_names["#active_user_id"] = "active_user_id"
                    expression_attribute_values[":active_user_id"] = current_alert.user_id
            else:
                remove_expression_parts.append("#active_user_id")
                expression_attribute_names["#active_user_id"] = "active_user_id"

        update_expression_parts.append("#updated_at = :updated_at")
        expression_attribute_names["#updated_at"] = "updated_at"
        expression_attribute_values[":updated_at"] = datetime.now(UTC).isoformat()

        update_expression = "SET " + ", ".join(update_expression_parts)
        if remove_expression_parts:
            update_expression += " REMOVE " + ", ".join(remove_expression_parts)

        try:
            response = self.table.update_item(
                Key={"alert_id": alert_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW",
            )
            updated_item = response.get("Attributes")

            if updated_item:
                logger.info("alert_updated", alert_id=alert_id)
                return self.mapper.to_entity(updated_item)

            return await self.find_by_id(alert_id)

        except Exception as e:
            logger.error("alert_update_error", alert_id=alert_id, error=str(e))
            return None

    async def find_duplicate(
        self,
        user_id: str,
        target_currency: str,
        condition: str,
        rate_type: str,
    ) -> Optional[Alert]:
        """
        Find an existing alert with the same parameters.

        Useful for checking duplicates before creating new alerts.
        """
        alerts = await self.find_by_user(user_id, is_active=True)

        for alert in alerts:
            if (
                alert.target_currency == target_currency
                and alert.condition == condition
                and alert.rate_type == rate_type
            ):
                return alert

        return None


__all__ = ["DynamoDBAlertRepository", "DuplicateAlertError"]
