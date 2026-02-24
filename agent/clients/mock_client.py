"""Fixture-backed mock Ghostfolio client for unit tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from agent.clients.ghostfolio_client import GhostfolioClientError, VALID_DATE_RANGES


class MockGhostfolioClient:
    """In-memory mock client that mirrors GhostfolioClient's public interface.

    Args:
        fixture_dir: Optional directory path containing JSON fixtures.
        performance_by_range: Optional preloaded performance fixtures by range.
        portfolio_details: Optional preloaded portfolio details response.
        portfolio_holdings: Optional preloaded portfolio holdings response.
        orders: Optional preloaded orders response.
    """

    def __init__(
        self,
        fixture_dir: str | Path | None = None,
        *,
        performance_by_range: dict[str, dict[str, Any]] | None = None,
        portfolio_details: dict[str, Any] | None = None,
        portfolio_holdings: dict[str, Any] | None = None,
        orders: dict[str, Any] | None = None,
    ) -> None:
        self._fixture_dir = (
            Path(fixture_dir)
            if fixture_dir is not None
            else Path(__file__).resolve().parents[1] / "tests" / "fixtures"
        )

        default_performance = self._load_json_fixture("performance_ytd.json")
        self._performance_by_range = performance_by_range or {"ytd": default_performance}
        self._portfolio_details = portfolio_details or self._load_json_fixture("portfolio_details.json")
        self._portfolio_holdings = (
            portfolio_holdings or self._load_json_fixture("portfolio_holdings.json")
        )
        self._orders = orders or self._load_json_fixture("orders.json")

    async def get_portfolio_performance(self, time_period: str) -> dict[str, Any]:
        """Returns a deterministic portfolio performance response."""
        self._validate_date_range(time_period)
        response = self._performance_by_range.get(time_period) or self._performance_by_range.get("ytd")
        if response is None:
            raise GhostfolioClientError(
                "API_ERROR",
                detail="No performance fixture configured for requested range.",
            )

        return copy.deepcopy(response)

    async def get_portfolio_details(self) -> dict[str, Any]:
        """Returns a deterministic portfolio details response."""
        return copy.deepcopy(self._portfolio_details)

    async def get_portfolio_holdings(self) -> dict[str, Any]:
        """Returns a deterministic portfolio holdings response."""
        return copy.deepcopy(self._portfolio_holdings)

    async def get_orders(self, date_range: str | None = None) -> dict[str, Any]:
        """Returns a deterministic orders response."""
        if date_range is not None:
            self._validate_date_range(date_range)

        return copy.deepcopy(self._orders)

    def _validate_date_range(self, value: str) -> None:
        if value not in VALID_DATE_RANGES:
            raise GhostfolioClientError("INVALID_TIME_PERIOD", detail=f"Unsupported range: {value}")

    def _load_json_fixture(self, filename: str) -> dict[str, Any]:
        fixture_path = self._fixture_dir / filename
        if not fixture_path.exists():
            raise ValueError(f"Fixture file not found: {fixture_path}")

        with fixture_path.open("r", encoding="utf-8") as fixture_file:
            payload = json.load(fixture_file)

        if not isinstance(payload, dict):
            raise ValueError(f"Fixture file must contain a JSON object: {fixture_path}")

        return payload
