"""DLQ Handler — logs failed check_alerts events to CloudWatch."""

import json

import structlog

logger = structlog.get_logger(__name__)


def lambda_handler(event: dict, context: object) -> None:
    """Process failed events from the check_alerts DLQ.

    Each SQS record contains the original EventBridge event that failed.
    We log the full payload so it is searchable in CloudWatch Logs.
    """
    for record in event.get("Records", []):
        body = record.get("body", "{}")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}

        logger.error(
            "dlq_event_received",
            message_id=record.get("messageId"),
            source=payload.get("source"),
            detail_type=payload.get("detail-type"),
            detail=payload.get("detail"),
            receipt_handle=record.get("receiptHandle"),
        )
