import os
import pytest
import boto3
from moto import mock_aws
from unittest.mock import MagicMock


def pytest_configure(config):
    if "ALERTS_TABLE_NAME" not in os.environ:
        os.environ["ALERTS_TABLE_NAME"] = "currency-alerts"
    if "USERS_TABLE_NAME" not in os.environ:
        os.environ["USERS_TABLE_NAME"] = "users"
    if "EXCHANGE_RATES_TABLE_NAME" not in os.environ:
        os.environ["EXCHANGE_RATES_TABLE_NAME"] = "exchange-rates"
    if "RATE_HISTORY_TABLE_NAME" not in os.environ:
        os.environ["RATE_HISTORY_TABLE_NAME"] = "rate-history"
    if "NOTIFICATION_HISTORY_TABLE_NAME" not in os.environ:
        os.environ["NOTIFICATION_HISTORY_TABLE_NAME"] = "notification-history"
    if "TELEGRAM_BOT_TOKEN" not in os.environ:
        os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
    if "KOREAEXIM_AUTHKEY" not in os.environ:
        os.environ["KOREAEXIM_AUTHKEY"] = "test-authkey"
    if "AWS_REGION" not in os.environ:
        os.environ["AWS_REGION"] = "ap-northeast-2"
    if "EVENTBRIDGE_BUS" not in os.environ:
        os.environ["EVENTBRIDGE_BUS"] = "currency-events"
    if "SECRET_KEY" not in os.environ:
        os.environ["SECRET_KEY"] = "test-secret-key"
    
    mock_eb_client = MagicMock()
    original_boto3_client = boto3.client

    def mock_boto3_client(service_name, **kwargs):
        if service_name == 'events':
            return mock_eb_client
        return original_boto3_client(service_name, **kwargs)
    
    boto3.client = mock_boto3_client


@pytest.fixture(scope="session")
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-2"


@pytest.fixture(scope="function")
def dynamodb_client(aws_credentials):
    with mock_aws():
        yield boto3.client("dynamodb", region_name="ap-northeast-2")


@pytest.fixture(scope="function")
def alerts_table(dynamodb_client):
    table_name = "currency-alerts"
    dynamodb_client.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {"AttributeName": "alert_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "base_currency", "AttributeType": "S"},
            {"AttributeName": "active_user_id", "AttributeType": "S"},
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
            # Sparse index: only items with active_user_id are indexed
            {
                "IndexName": "active_user_id-index",
                "KeySchema": [{"AttributeName": "active_user_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    os.environ["ALERTS_TABLE_NAME"] = table_name
    return table_name


@pytest.fixture(scope="function")
def users_table(dynamodb_client):
    table_name = "users"
    dynamodb_client.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"},
            {"AttributeName": "google_id", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "email-index",
                "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            # Sparse: only Google users have google_id
            {
                "IndexName": "google-index",
                "KeySchema": [{"AttributeName": "google_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    os.environ["USERS_TABLE_NAME"] = table_name
    return table_name


@pytest.fixture(scope="function")
def notification_history_table(dynamodb_client):
    table_name = "notification-history"
    dynamodb_client.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "currency", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "currency-index",
                "KeySchema": [{"AttributeName": "currency", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    os.environ["NOTIFICATION_HISTORY_TABLE_NAME"] = table_name
    return table_name


@pytest.fixture(scope="function")
def rate_history_table(dynamodb_client):
    table_name = "rate-history"
    dynamodb_client.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {"AttributeName": "currency_code", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "currency_code", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    os.environ["RATE_HISTORY_TABLE_NAME"] = table_name
    return table_name
