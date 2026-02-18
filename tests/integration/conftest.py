"""
Integration Test Fixtures.

Fixtures for integration tests - uses real database and services.
These fixtures build on the root conftest.py database fixtures.
"""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from modules.backend.core.database import get_db_session


# =============================================================================
# API Client Fixtures
# =============================================================================


@pytest.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create a test client with database session override.

    The client uses the test database session, ensuring all API
    operations use the same session that gets rolled back after the test.

    Usage:
        async def test_health_endpoint(client: AsyncClient):
            response = await client.get("/health")
            assert response.status_code == 200
    """
    # Override the database session dependency
    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    with patch("modules.backend.core.config.get_settings") as mock_secrets, \
         patch("modules.backend.core.config.get_app_config") as mock_config, \
         patch("modules.backend.core.security.get_settings") as mock_security_settings, \
         patch("modules.backend.core.security.get_app_config") as mock_security_config:
        mock_secrets.return_value = _create_mock_settings()
        mock_security_settings.return_value = _create_mock_settings()
        mock_app_config = _create_mock_app_config()
        mock_config.return_value = mock_app_config
        mock_security_config.return_value = mock_app_config

        from modules.backend.main import create_app

        app = create_app()
        app.dependency_overrides[get_db_session] = override_get_db_session

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as test_client:
            yield test_client

        app.dependency_overrides.clear()


@pytest.fixture
async def client_no_db() -> AsyncGenerator[AsyncClient, None]:
    """
    Create a test client without database dependency override.

    Use this for testing endpoints that don't require database access
    (e.g., health checks, static responses).

    Note: This requires mocking get_settings since no .env exists.
    """
    with patch("modules.backend.core.config.get_settings") as mock_secrets, \
         patch("modules.backend.core.config.get_app_config") as mock_config, \
         patch("modules.backend.core.security.get_settings") as mock_security_settings, \
         patch("modules.backend.core.security.get_app_config") as mock_security_config:
        mock_secrets.return_value = _create_mock_settings()
        mock_security_settings.return_value = _create_mock_settings()
        mock_app_config = _create_mock_app_config()
        mock_config.return_value = mock_app_config
        mock_security_config.return_value = mock_app_config

        from modules.backend.main import create_app

        app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as test_client:
            yield test_client


# =============================================================================
# Mock Settings Helper
# =============================================================================


def _create_mock_settings() -> Any:
    """Create a mock secrets object for testing."""
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.db_password = "test_pass"
    settings.redis_password = ""
    settings.jwt_secret = "test-secret-key"
    settings.api_key_salt = "test-salt"
    settings.telegram_bot_token = ""
    settings.telegram_webhook_secret = ""
    return settings


def _create_mock_app_config() -> Any:
    """Create a mock app config object for testing."""
    from unittest.mock import MagicMock

    config = MagicMock()
    config.application = {
        "name": "Test Application",
        "version": "1.0.0",
        "description": "Test application",
        "environment": "test",
        "debug": True,
        "server": {"host": "127.0.0.1", "port": 8000},
        "cors": {"origins": ["http://localhost:3000"]},
        "telegram": {"webhook_path": "/webhook/telegram", "authorized_users": []},
    }
    config.database = {
        "host": "localhost",
        "port": 5432,
        "name": "test_db",
        "user": "test_user",
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "echo": False,
        "redis": {"host": "localhost", "port": 6379, "db": 0},
    }
    config.logging = {
        "level": "WARNING",
        "format": "console",
        "handlers": {
            "console": {"enabled": True},
            "file": {"enabled": False, "max_bytes": 10485760, "backup_count": 5},
        },
    }
    config.features = {}
    config.security = {
        "jwt": {
            "algorithm": "HS256",
            "access_token_expire_minutes": 30,
            "refresh_token_expire_days": 7,
        },
    }
    return config


# =============================================================================
# API Response Assertion Helpers
# =============================================================================


class ApiAssertions:
    """Helper class for API response assertions."""

    @staticmethod
    def assert_success(response: Any, expected_status: int = 200) -> dict[str, Any]:
        """
        Assert API response is successful.

        Args:
            response: httpx Response object
            expected_status: Expected HTTP status code

        Returns:
            Response JSON data

        Raises:
            AssertionError: If response is not successful
        """
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}: "
            f"{response.text}"
        )
        data = response.json()
        assert data.get("success") is True, f"Response not successful: {data}"
        return data

    @staticmethod
    def assert_error(
        response: Any,
        expected_status: int,
        expected_code: str | None = None,
    ) -> dict[str, Any]:
        """
        Assert API response is an error.

        Args:
            response: httpx Response object
            expected_status: Expected HTTP status code
            expected_code: Expected error code (optional)

        Returns:
            Response JSON data

        Raises:
            AssertionError: If response is not an error or codes don't match
        """
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}: "
            f"{response.text}"
        )
        data = response.json()
        assert data.get("success") is False, f"Response should be error: {data}"
        assert data.get("error") is not None, f"Missing error details: {data}"

        if expected_code:
            actual_code = data["error"].get("code")
            assert actual_code == expected_code, (
                f"Expected error code {expected_code}, got {actual_code}"
            )

        return data

    @staticmethod
    def assert_validation_error(
        response: Any,
        field: str | None = None,
    ) -> dict[str, Any]:
        """
        Assert API response is a validation error (422).

        Args:
            response: httpx Response object
            field: Expected field with validation error (optional)

        Returns:
            Response JSON data
        """
        data = ApiAssertions.assert_error(response, 422, "VAL_REQUEST_INVALID")

        if field:
            errors = data["error"].get("details", {}).get("validation_errors", [])
            fields = [e.get("field", "") for e in errors]
            assert any(field in f for f in fields), (
                f"Expected validation error for field '{field}', "
                f"got errors for: {fields}"
            )

        return data


@pytest.fixture
def api() -> ApiAssertions:
    """Provide API assertion helpers."""
    return ApiAssertions()


# =============================================================================
# Authentication Fixtures
# =============================================================================


@pytest.fixture
def auth_headers(test_settings: dict[str, Any]) -> dict[str, str]:
    """
    Provide authentication headers for API requests.

    Creates a valid JWT token for testing authenticated endpoints.

    Usage:
        async def test_protected_endpoint(client: AsyncClient, auth_headers: dict):
            response = await client.get("/api/v1/me", headers=auth_headers)
            assert response.status_code == 200
    """
    from modules.backend.core.security import create_access_token

    # Create a test token with mock user data
    token = create_access_token(
        data={"sub": "test-user-id", "email": "test@example.com"},
    )
    return {"Authorization": f"Bearer {token}"}
