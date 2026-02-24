"""Async Ghostfolio API client with Bearer auth and token refresh."""

from __future__ import annotations

from types import TracebackType
from typing import Any, Final

import httpx

from agent.auth import clear_bearer_token_cache, get_bearer_token

VALID_DATE_RANGES: Final[set[str]] = {"1d", "wtd", "mtd", "ytd", "1y", "5y", "max"}


class GhostfolioClientError(Exception):
    """Structured client error consumed by tools as error codes."""

    def __init__(
        self,
        error_code: str,
        *,
        status: int | None = None,
        detail: str | None = None,
    ) -> None:
        self.error_code = error_code
        self.status = status
        self.detail = detail
        super().__init__(self.__str__())

    def __str__(self) -> str:
        parts = [self.error_code]
        if self.status is not None:
            parts.append(f"status={self.status}")
        if self.detail:
            parts.append(self.detail)

        return " | ".join(parts)


class GhostfolioClient:
    """Client used by tools to query Ghostfolio portfolio endpoints.

    Args:
        base_url: Ghostfolio base URL.
        access_token: Ghostfolio security token for anonymous auth exchange.
        client: Optional injected async client for testing.
        timeout_seconds: Timeout for client-created AsyncClient.
    """

    def __init__(
        self,
        base_url: str,
        access_token: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        normalized_base_url = base_url.rstrip("/")
        if not normalized_base_url:
            raise ValueError("base_url is required.")

        normalized_access_token = access_token.strip()
        if not normalized_access_token:
            raise ValueError("access_token is required.")

        self.base_url = normalized_base_url
        self.access_token = normalized_access_token
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None
        self._bearer_token: str | None = None

    async def __aenter__(self) -> "GhostfolioClient":
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Closes the internal HTTP client if this instance owns it."""
        if self._owns_client:
            await self._client.aclose()

    async def get_portfolio_performance(self, time_period: str) -> dict[str, Any]:
        """Returns portfolio performance for a given date range."""
        self._validate_date_range(time_period)
        return await self._request_json(
            "/api/v2/portfolio/performance",
            params={"range": time_period},
        )

    async def get_portfolio_details(self) -> dict[str, Any]:
        """Returns portfolio details from Ghostfolio."""
        return await self._request_json("/api/v1/portfolio/details")

    async def get_portfolio_holdings(self) -> dict[str, Any]:
        """Returns portfolio holdings from Ghostfolio."""
        return await self._request_json("/api/v1/portfolio/holdings")

    async def get_orders(self, date_range: str | None = None) -> dict[str, Any]:
        """Returns portfolio activities/orders with optional range filter."""
        params: dict[str, str] | None = None
        if date_range is not None:
            self._validate_date_range(date_range)
            params = {"range": date_range}

        return await self._request_json("/api/v1/order", params=params)

    def _validate_date_range(self, value: str) -> None:
        """Validates Ghostfolio-supported date range values."""
        if value not in VALID_DATE_RANGES:
            raise GhostfolioClientError("INVALID_TIME_PERIOD", detail=f"Unsupported range: {value}")

    async def _request_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        token = self._bearer_token or await self._ensure_token()
        response = await self._send_get(path=path, params=params, bearer_token=token)

        if response.status_code == 401:
            clear_bearer_token_cache(self.base_url)
            refreshed_token = await self._ensure_token(force_refresh=True)
            response = await self._send_get(
                path=path,
                params=params,
                bearer_token=refreshed_token,
            )
            if response.status_code == 401:
                raise GhostfolioClientError("AUTH_FAILED", status=401)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code if error.response else None
            raise GhostfolioClientError("API_ERROR", status=status_code) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise GhostfolioClientError(
                "API_ERROR",
                detail="Ghostfolio returned a non-JSON response.",
            ) from error

        if not isinstance(payload, dict):
            raise GhostfolioClientError(
                "API_ERROR",
                detail="Ghostfolio response must be a JSON object.",
            )

        return payload

    async def _send_get(
        self,
        *,
        path: str,
        params: dict[str, str] | None,
        bearer_token: str,
    ) -> httpx.Response:
        try:
            return await self._client.get(
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {bearer_token}"},
                params=params,
            )
        except httpx.TimeoutException as error:
            raise GhostfolioClientError("API_TIMEOUT") from error
        except httpx.RequestError as error:
            raise GhostfolioClientError("API_ERROR", detail=str(error)) from error

    async def _ensure_token(self, *, force_refresh: bool = False) -> str:
        try:
            bearer_token = await get_bearer_token(
                self.base_url,
                self.access_token,
                client=self._client,
                force_refresh=force_refresh,
            )
        except httpx.TimeoutException as error:
            raise GhostfolioClientError("API_TIMEOUT") from error
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code if error.response else None
            if status_code == 401:
                raise GhostfolioClientError("AUTH_FAILED", status=status_code) from error
            raise GhostfolioClientError("API_ERROR", status=status_code) from error
        except ValueError as error:
            raise GhostfolioClientError("AUTH_FAILED", detail=str(error)) from error

        self._bearer_token = bearer_token
        return bearer_token
