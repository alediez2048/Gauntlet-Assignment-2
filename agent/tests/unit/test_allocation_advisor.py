import json
from pathlib import Path
from typing import Any

import pytest

from agent.clients.ghostfolio_client import GhostfolioClientError
from agent.clients.mock_client import MockGhostfolioClient
from agent.tools.allocation_advisor import advise_asset_allocation


class SpyDetailsClient:
    def __init__(self) -> None:
        self.call_count = 0

    async def get_portfolio_details(self) -> dict[str, Any]:
        self.call_count += 1
        return {"holdings": {}}


class ErroringDetailsClient:
    def __init__(self, error: Exception) -> None:
        self.call_count = 0
        self.error = error

    async def get_portfolio_details(self) -> dict[str, Any]:
        self.call_count += 1
        raise self.error


def _load_fixture_payload(fixture_path: Path) -> dict[str, Any]:
    with fixture_path.open("r", encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)

    assert isinstance(payload, dict)
    return payload


@pytest.mark.asyncio
async def test_advise_asset_allocation_happy_path_matches_expected_drift(
    fixtures_dir: Path,
) -> None:
    details_payload = _load_fixture_payload(fixtures_dir / "portfolio_details_allocation_mix.json")
    mock_client = MockGhostfolioClient(portfolio_details=details_payload)

    result = await advise_asset_allocation(mock_client, target_profile="balanced")

    assert result.success is True
    assert result.error is None
    assert result.data is not None
    assert result.metadata["source"] == "allocation_advisor"
    assert result.metadata["target_profile"] == "balanced"

    assert result.data["target_profile"] == "balanced"
    assert result.data["current_allocation"] == {
        "EQUITY": 65.0,
        "FIXED_INCOME": 20.0,
        "LIQUIDITY": 10.0,
        "COMMODITY": 5.0,
        "REAL_ESTATE": 0.0,
        "ALTERNATIVE_INVESTMENT": 0.0,
    }
    assert result.data["target_allocation"] == {
        "EQUITY": 60.0,
        "FIXED_INCOME": 30.0,
        "LIQUIDITY": 10.0,
        "COMMODITY": 0.0,
        "REAL_ESTATE": 0.0,
        "ALTERNATIVE_INVESTMENT": 0.0,
    }
    assert result.data["drift"] == {
        "EQUITY": 5.0,
        "FIXED_INCOME": -10.0,
        "LIQUIDITY": 0.0,
        "COMMODITY": 5.0,
        "REAL_ESTATE": 0.0,
        "ALTERNATIVE_INVESTMENT": 0.0,
    }
    assert result.data["rebalancing_suggestions"] == [
        "Consider trimming Commodity by about 5.0% to align with the balanced profile.",
        "Consider increasing Fixed Income by about 10.0% to align with the balanced profile.",
    ]
    assert result.data["holdings_count"] == 5
    assert result.data["disclaimer"] == "Analysis for informational purposes only. Not financial advice."


@pytest.mark.asyncio
async def test_advise_asset_allocation_flags_concentration_warning(fixtures_dir: Path) -> None:
    details_payload = _load_fixture_payload(fixtures_dir / "portfolio_details_allocation_mix.json")
    mock_client = MockGhostfolioClient(portfolio_details=details_payload)

    result = await advise_asset_allocation(mock_client, target_profile="balanced")

    assert result.success is True
    assert result.data is not None
    assert result.data["concentration_warnings"] == [
        {"symbol": "AAPL", "pct_of_portfolio": 45.0, "threshold": 25.0}
    ]


@pytest.mark.asyncio
async def test_advise_asset_allocation_invalid_profile_short_circuits_api_call() -> None:
    spy_client = SpyDetailsClient()

    result = await advise_asset_allocation(spy_client, target_profile="income")

    assert result.success is False
    assert result.data is None
    assert result.error == "INVALID_TARGET_PROFILE"
    assert result.metadata["target_profile"] == "income"
    assert spy_client.call_count == 0


@pytest.mark.asyncio
async def test_advise_asset_allocation_empty_portfolio_returns_error() -> None:
    mock_client = MockGhostfolioClient(portfolio_details={"holdings": {}})

    result = await advise_asset_allocation(mock_client, target_profile="balanced")

    assert result.success is False
    assert result.data is None
    assert result.error == "EMPTY_PORTFOLIO"
    assert result.metadata["target_profile"] == "balanced"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_code", "status"),
    [("API_TIMEOUT", None), ("API_ERROR", 500), ("AUTH_FAILED", 401)],
)
async def test_advise_asset_allocation_maps_client_error_codes(
    error_code: str, status: int | None
) -> None:
    failing_client = ErroringDetailsClient(
        GhostfolioClientError(error_code, status=status, detail="internal detail")
    )

    result = await advise_asset_allocation(failing_client, target_profile="aggressive")

    assert result.success is False
    assert result.data is None
    assert result.error == error_code
    assert result.metadata["target_profile"] == "aggressive"
    if status is None:
        assert "status" not in result.metadata
    else:
        assert result.metadata["status"] == status
    assert "internal detail" not in str(result.metadata)


@pytest.mark.asyncio
async def test_advise_asset_allocation_maps_unexpected_exceptions_to_api_error() -> None:
    failing_client = ErroringDetailsClient(RuntimeError("unexpected low-level detail"))

    result = await advise_asset_allocation(failing_client, target_profile="balanced")

    assert result.success is False
    assert result.data is None
    assert result.error == "API_ERROR"
    assert result.metadata["target_profile"] == "balanced"
    assert "unexpected low-level detail" not in str(result.metadata)
