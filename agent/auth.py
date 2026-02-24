"""Ghostfolio authentication helpers for Bearer token lifecycle."""

from __future__ import annotations

import os
from typing import Final

import httpx
from cachetools import TTLCache

AUTH_ENDPOINT: Final[str] = "/api/v1/auth/anonymous"
AUTH_CACHE_TTL_SECONDS: Final[int] = 60
AUTH_CACHE_MAXSIZE: Final[int] = 8

_bearer_token_cache: TTLCache[str, str] = TTLCache(
    maxsize=AUTH_CACHE_MAXSIZE, ttl=AUTH_CACHE_TTL_SECONDS
)


def _normalize_base_url(base_url: str) -> str:
    """Returns a normalized base URL without trailing slash."""
    return base_url.rstrip("/")


def get_access_token_from_env() -> str:
    """Returns the Ghostfolio security token from environment variables.

    Returns:
        The non-empty Ghostfolio access token.

    Raises:
        ValueError: If `GHOSTFOLIO_ACCESS_TOKEN` is not configured.
    """
    access_token = os.getenv("GHOSTFOLIO_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise ValueError("GHOSTFOLIO_ACCESS_TOKEN is required at runtime.")

    return access_token


def clear_bearer_token_cache(base_url: str | None = None) -> None:
    """Clears the cached bearer token for one base URL or all URLs.

    Args:
        base_url: Base URL to clear from cache. If omitted, clears all tokens.
    """
    if base_url is None:
        _bearer_token_cache.clear()
        return

    _bearer_token_cache.pop(_normalize_base_url(base_url), None)


async def get_bearer_token(
    base_url: str,
    access_token: str | None = None,
    *,
    client: httpx.AsyncClient | None = None,
    force_refresh: bool = False,
) -> str:
    """Fetches a Ghostfolio Bearer token and caches it by base URL.

    Args:
        base_url: Ghostfolio API base URL (e.g. `http://localhost:3333`).
        access_token: Ghostfolio security token. If omitted, reads from env.
        client: Optional shared async HTTP client, mainly for tests.
        force_refresh: When true, bypasses cache and fetches a fresh token.

    Returns:
        A Bearer token (`authToken`) string returned by Ghostfolio.

    Raises:
        ValueError: If inputs are invalid or response payload is malformed.
        httpx.HTTPError: If the auth request fails at HTTP/client level.
    """
    normalized_base_url = _normalize_base_url(base_url)
    if not normalized_base_url:
        raise ValueError("base_url is required.")

    if not force_refresh:
        cached_token = _bearer_token_cache.get(normalized_base_url)
        if cached_token:
            return cached_token

    resolved_access_token = (
        access_token.strip() if access_token is not None else get_access_token_from_env()
    )
    if not resolved_access_token:
        raise ValueError("GHOSTFOLIO_ACCESS_TOKEN is required at runtime.")

    owns_client = client is None
    http_client = client or httpx.AsyncClient()

    try:
        response = await http_client.post(
            f"{normalized_base_url}{AUTH_ENDPOINT}",
            json={"accessToken": resolved_access_token}
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as error:
            raise ValueError("Ghostfolio auth response is not valid JSON.") from error
    finally:
        if owns_client:
            await http_client.aclose()

    bearer_token = payload.get("authToken")
    if not isinstance(bearer_token, str) or not bearer_token:
        raise ValueError("Ghostfolio auth response did not include authToken.")

    _bearer_token_cache[normalized_base_url] = bearer_token
    return bearer_token
