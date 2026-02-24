"""Shared fixtures for agent unit and integration tests."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio

from agent.auth import clear_bearer_token_cache
from agent.clients.ghostfolio_client import GhostfolioClient
from agent.clients.mock_client import MockGhostfolioClient


@pytest.fixture(autouse=True)
def reset_bearer_token_cache() -> None:
    """Ensures auth token cache isolation between tests."""
    clear_bearer_token_cache()
    yield
    clear_bearer_token_cache()


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Returns the absolute path to JSON fixtures used by tests."""
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def fixture_payloads(fixtures_dir: Path) -> dict[str, dict[str, Any]]:
    """Loads canonical JSON fixture payloads once per test session."""

    def load_fixture(filename: str) -> dict[str, Any]:
        fixture_path = fixtures_dir / filename
        with fixture_path.open("r", encoding="utf-8") as fixture_file:
            payload = json.load(fixture_file)

        if not isinstance(payload, dict):
            raise ValueError(f"Fixture file must contain a JSON object: {fixture_path}")

        return payload

    return {
        "performance_ytd": load_fixture("performance_ytd.json"),
        "portfolio_details": load_fixture("portfolio_details.json"),
        "portfolio_holdings": load_fixture("portfolio_holdings.json"),
        "orders": load_fixture("orders.json"),
    }


@pytest.fixture
def mock_ghostfolio_client(fixtures_dir: Path) -> MockGhostfolioClient:
    """Returns a fixture-backed mock client for tool unit tests."""
    return MockGhostfolioClient(fixture_dir=fixtures_dir)


@pytest_asyncio.fixture
async def ghostfolio_client() -> AsyncIterator[GhostfolioClient]:
    """Returns a real client fixture configured from environment variables."""
    base_url = os.getenv("GHOSTFOLIO_API_URL", "http://localhost:3333")
    access_token = os.getenv("GHOSTFOLIO_ACCESS_TOKEN", "test-token")

    async with httpx.AsyncClient() as http_client:
        client = GhostfolioClient(base_url=base_url, access_token=access_token, client=http_client)
        yield client
