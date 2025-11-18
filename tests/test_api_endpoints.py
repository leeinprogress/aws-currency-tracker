import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.alerts import get_alert_service
from app.api.v1.auth import get_user_service
from app.core.dependencies import get_current_user
from app.db.models.alert import Alert
from app.db.models.user import User
from app.schemas.alert import AlertCreate, AlertUpdate
from app.schemas.user import UserCreate


class FakeAlertService:
    """Simple in-memory alert service used for FastAPI endpoint tests."""

    def __init__(self):
        self.alerts: Dict[str, Alert] = {}

    def add_alert(self, alert: Alert) -> Alert:
        self.alerts[alert.alert_id] = alert
        return alert

    async def create_alert(self, alert_data: AlertCreate) -> Alert:
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            user_id=alert_data.user_id or "",
            telegram_chat_id=alert_data.telegram_chat_id or "",
            base_currency=alert_data.base_currency,
            target_currency=alert_data.target_currency,
            target_rate=alert_data.target_rate,
            condition=alert_data.condition,
            rate_type=alert_data.rate_type,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.alerts[alert.alert_id] = alert
        return alert

    async def list_alerts(
        self,
        user_id: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[Alert]:
        alerts = list(self.alerts.values())
        if user_id is not None:
            alerts = [alert for alert in alerts if alert.user_id == user_id]
        if is_active is not None:
            alerts = [alert for alert in alerts if alert.is_active == is_active]
        return alerts

    async def get_alert(self, alert_id: str) -> Optional[Alert]:
        return self.alerts.get(alert_id)

    async def update_alert(self, alert_id: str, update_data: AlertUpdate) -> Optional[Alert]:
        alert = self.alerts.get(alert_id)
        if not alert:
            return None
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(alert, key, value)
        alert.updated_at = datetime.now(timezone.utc)
        return alert

    async def delete_alert(self, alert_id: str) -> bool:
        return self.alerts.pop(alert_id, None) is not None

    async def toggle_alert(self, alert_id: str) -> Optional[Alert]:
        alert = self.alerts.get(alert_id)
        if not alert:
            return None
        alert.is_active = not alert.is_active
        alert.updated_at = datetime.now(timezone.utc)
        return alert


class FakeUserService:
    """Simple in-memory user service used for FastAPI auth endpoint tests."""

    def __init__(self):
        self.users: Dict[str, User] = {}
        self.emails: Dict[str, str] = {}  # email -> user_id mapping

    def add_user(self, user: User) -> User:
        self.users[user.user_id] = user
        self.emails[user.email.lower()] = user.user_id
        return user

    async def create_user(self, user_data: UserCreate) -> User:
        # Check if user already exists
        if user_data.email.lower() in self.emails:
            raise ValueError("User with this email already exists")

        user = User(
            user_id=str(uuid.uuid4()),
            email=user_data.email,
            telegram_chat_id=user_data.telegram_chat_id,
            hashed_password=f"hashed_{user_data.password}",  # Simplified for testing
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.add_user(user)
        return user

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user_id = self.emails.get(email.lower())
        if not user_id:
            return None
        user = self.users.get(user_id)
        if not user:
            return None
        # Simplified password check for testing
        if user.hashed_password != f"hashed_{password}":
            return None
        if not user.is_active:
            return None
        return user

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)


@pytest.fixture
def test_user() -> User:
    return User(
        user_id="user-123",
        email="test@example.com",
        telegram_chat_id="chat-123",
        hashed_password="hashed",
        is_active=True,
    )


@pytest.fixture
def fake_user_service() -> FakeUserService:
    return FakeUserService()


@pytest.fixture
def fake_alert_service() -> FakeAlertService:
    return FakeAlertService()


@pytest.fixture
def api_client(fake_alert_service: FakeAlertService, test_user: User):
    async def override_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_alert_service] = lambda: fake_alert_service

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()
    fake_alert_service.alerts.clear()


def test_create_alert_returns_created_alert(api_client: TestClient):
    payload = {
        "target_currency": "usd",
        "target_rate": 1300.5,
        "condition": "above",
        "rate_type": "TTS",
    }

    response = api_client.post("/api/v1/alerts", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == "user-123"
    assert body["base_currency"] == "KRW"
    assert body["target_currency"] == "USD"
    assert body["condition"] == "above"
    assert "alert_id" in body


def test_list_alerts_filters_by_active_flag(
    api_client: TestClient,
    fake_alert_service: FakeAlertService,
    test_user: User,
):
    active_alert = Alert(
        alert_id="alert-active",
        user_id=test_user.user_id,
        telegram_chat_id=test_user.telegram_chat_id,
        base_currency="KRW",
        target_currency="USD",
        target_rate=1200.0,
        condition="above",
        rate_type="TTS",
        is_active=True,
    )
    inactive_alert = Alert(
        alert_id="alert-inactive",
        user_id=test_user.user_id,
        telegram_chat_id=test_user.telegram_chat_id,
        base_currency="KRW",
        target_currency="EUR",
        target_rate=1400.0,
        condition="below",
        rate_type="TTB",
        is_active=False,
    )

    fake_alert_service.add_alert(active_alert)
    fake_alert_service.add_alert(inactive_alert)

    response = api_client.get("/api/v1/alerts", params={"is_active": True})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["alerts"][0]["alert_id"] == "alert-active"
    assert body["alerts"][0]["target_currency"] == "USD"


def test_get_alert_forbidden_for_other_user(
    api_client: TestClient,
    fake_alert_service: FakeAlertService,
):
    other_user_alert = Alert(
        alert_id="alert-other-user",
        user_id="different-user",
        telegram_chat_id="chat-other",
        base_currency="KRW",
        target_currency="JPY",
        target_rate=900.0,
        condition="below",
        rate_type="DEAL_BAS_R",
        is_active=True,
    )
    fake_alert_service.add_alert(other_user_alert)

    response = api_client.get("/api/v1/alerts/alert-other-user")

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to access this alert"


# ==================== Auth Endpoint Tests ====================

@pytest.fixture
def auth_client(fake_user_service: FakeUserService):
    """Client for auth endpoints without authentication requirement."""
    app.dependency_overrides[get_user_service] = lambda: fake_user_service

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()
    fake_user_service.users.clear()
    fake_user_service.emails.clear()


def test_register_user_success(auth_client: TestClient):
    """Test successful user registration."""
    payload = {
        "email": "newuser@example.com",
        "password": "securepass123",
        "telegram_chat_id": "chat-456",
    }

    response = auth_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newuser@example.com"
    assert body["telegram_chat_id"] == "chat-456"
    assert body["is_active"] is True
    assert "user_id" in body
    assert "password" not in body  # Password should not be in response


def test_register_user_duplicate_email(auth_client: TestClient, fake_user_service: FakeUserService):
    """Test registration with duplicate email returns 400."""
    existing_user = User(
        user_id="existing-123",
        email="existing@example.com",
        telegram_chat_id="chat-existing",
        hashed_password="hashed",
        is_active=True,
    )
    fake_user_service.add_user(existing_user)

    payload = {
        "email": "existing@example.com",
        "password": "password123",
        "telegram_chat_id": "chat-new",
    }

    response = auth_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_register_user_invalid_email(auth_client: TestClient):
    """Test registration with invalid email format returns 422."""
    payload = {
        "email": "not-an-email",
        "password": "password123",
        "telegram_chat_id": "chat-123",
    }

    response = auth_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


def test_register_user_short_password(auth_client: TestClient):
    """Test registration with password shorter than 8 characters returns 422."""
    payload = {
        "email": "user@example.com",
        "password": "short",  # Less than 8 characters
        "telegram_chat_id": "chat-123",
    }

    response = auth_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


def test_login_success(auth_client: TestClient, fake_user_service: FakeUserService):
    """Test successful login returns access token."""
    # Create a user first
    user = User(
        user_id="login-user-123",
        email="login@example.com",
        telegram_chat_id="chat-login",
        hashed_password="hashed_correctpass",
        is_active=True,
    )
    fake_user_service.add_user(user)

    # Login with correct credentials
    response = auth_client.post(
        "/api/v1/auth/login",
        data={
            "username": "login@example.com",  # OAuth2PasswordRequestForm uses 'username' field
            "password": "correctpass",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert "user" in body
    assert body["user"]["email"] == "login@example.com"
    assert body["user"]["user_id"] == "login-user-123"


def test_login_wrong_password(auth_client: TestClient, fake_user_service: FakeUserService):
    """Test login with wrong password returns 401."""
    user = User(
        user_id="login-user-123",
        email="login@example.com",
        telegram_chat_id="chat-login",
        hashed_password="hashed_correctpass",
        is_active=True,
    )
    fake_user_service.add_user(user)

    response = auth_client.post(
        "/api/v1/auth/login",
        data={
            "username": "login@example.com",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_login_nonexistent_user(auth_client: TestClient):
    """Test login with non-existent email returns 401."""
    response = auth_client.post(
        "/api/v1/auth/login",
        data={
            "username": "nonexistent@example.com",
            "password": "anypassword",
        },
    )

    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_login_inactive_user(auth_client: TestClient, fake_user_service: FakeUserService):
    """Test login with inactive user returns 401."""
    user = User(
        user_id="inactive-user-123",
        email="inactive@example.com",
        telegram_chat_id="chat-inactive",
        hashed_password="hashed_password123",
        is_active=False,  # Inactive user
    )
    fake_user_service.add_user(user)

    response = auth_client.post(
        "/api/v1/auth/login",
        data={
            "username": "inactive@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

