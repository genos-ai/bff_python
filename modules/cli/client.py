"""
HTTP Client for CLI.

Provides async HTTP client for communicating with the backend API.
All requests include X-Frontend-ID: cli header for log routing.
"""

from typing import Any

import httpx

from modules.backend.core.config import get_server_base_url
from modules.backend.core.logging import get_logger, log_with_source

logger = get_logger(__name__)


class APIClient:
    """
    HTTP client for backend API communication.

    Features:
    - Automatic base URL from settings
    - X-Frontend-ID header for log routing
    - Structured logging of requests/responses
    - Error handling with context

    Usage:
        client = APIClient(source="cli")
        response = await client.get("/health")
        response = await client.post("/api/v1/users", json={"name": "test"})
    """

    def __init__(
        self,
        source: str,
        base_url: str | None = None,
        timeout: float | None = None,
    ):
        """
        Initialize the API client.

        Args:
            source: Frontend identifier for X-Frontend-ID header (cli, chat, tui, telegram).
            base_url: Backend API base URL. If None, reads from config/settings/application.yaml.
            timeout: Request timeout in seconds. If None, reads from config/settings/application.yaml.
        """
        config_base_url, config_timeout = get_server_base_url()

        self.source = source
        self.base_url = (base_url or config_base_url).rstrip("/")
        self.timeout = timeout if timeout is not None else config_timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"X-Frontend-ID": self.source},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make an HTTP request to the backend.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /health, /api/v1/users)
            **kwargs: Additional arguments for httpx

        Returns:
            httpx.Response

        Raises:
            httpx.HTTPError: On request failure
        """
        client = await self._get_client()

        log_with_source(
            logger,
            self.source,
            "debug",
            "API request",
            method=method,
            path=path,
        )

        try:
            response = await client.request(method, path, **kwargs)

            log_with_source(
                logger,
                self.source,
                "debug",
                "API response",
                method=method,
                path=path,
                status_code=response.status_code,
            )

            return response

        except httpx.HTTPError as e:
            log_with_source(
                logger,
                self.source,
                "error",
                "API request failed",
                method=method,
                path=path,
                error=str(e),
            )
            raise

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a GET request."""
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a POST request."""
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a PUT request."""
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a PATCH request."""
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a DELETE request."""
        return await self.request("DELETE", path, **kwargs)


# Module-level client instance
_client: APIClient | None = None


def get_api_client(source: str = "cli") -> APIClient:
    """Get or create the API client singleton."""
    global _client
    if _client is None:
        _client = APIClient(source=source)
    return _client


async def close_api_client() -> None:
    """Close the API client."""
    global _client
    if _client:
        await _client.close()
        _client = None
