
import os
import pytest
import boto3
from moto import mock_aws
from unittest.mock import MagicMock, patch


def pytest_configure(config):
    """Configure pytest - runs before test collection."""
    # Set required environment variables before any modules are imported
    # This prevents ValidationError when Settings() is instantiated at module level
    if "ALERTS_TABLE_NAME" not in os.environ:
        os.environ["ALERTS_TABLE_NAME"] = "currency-alerts"
    if "USERS_TABLE_NAME" not in os.environ:
        os.environ["USERS_TABLE_NAME"] = "users"
    # Set other optional environment variables with test defaults
    if "TELEGRAM_BOT_TOKEN" not in os.environ:
        os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
    if "KOREAEXIM_AUTHKEY" not in os.environ:
        os.environ["KOREAEXIM_AUTHKEY"] = "test-authkey"
    if "AWS_REGION" not in os.environ:
        os.environ["AWS_REGION"] = "us-east-1"
    if "EVENTBRIDGE_BUS" not in os.environ:
        os.environ["EVENTBRIDGE_BUS"] = "currency-events"
    if "SECRET_KEY" not in os.environ:
        os.environ["SECRET_KEY"] = "test-secret-key"
    
    # Mock boto3.client for EventBridge to avoid region errors during import
    # This is needed because fetch_rates.py creates eventbridge client at module level
    mock_eb_client = MagicMock()
    original_boto3_client = boto3.client
    def mock_boto3_client(service_name, **kwargs):
        if service_name == 'events':
            return mock_eb_client
        return original_boto3_client(service_name, **kwargs)
    
    # Patch boto3.client globally for tests
    boto3.client = mock_boto3_client


@pytest.fixture(scope="session")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture(scope="function")
def dynamodb_client(aws_credentials):
    """Mocked DynamoDB client."""
    with mock_aws():
        yield boto3.client("dynamodb", region_name="us-east-1")

@pytest.fixture(scope="function")
def alerts_table(dynamodb_client):
    """Create a mock DynamoDB table for alerts."""
    table_name = "currency-alerts"
    dynamodb_client.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {"AttributeName": "alert_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "base_currency", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "alert_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user_id-index",
                "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "base_currency-index",
                "KeySchema": [{"AttributeName": "base_currency", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    os.environ["ALERTS_TABLE_NAME"] = table_name
    return table_name

@pytest.fixture(scope="function")
def users_table(dynamodb_client):
    """Create a mock DynamoDB table for users."""
    table_name = "users"
    dynamodb_client.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "email-index",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    os.environ["USERS_TABLE_NAME"] = table_name
    return table_name
