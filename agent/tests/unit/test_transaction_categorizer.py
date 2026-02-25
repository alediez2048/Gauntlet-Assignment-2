import json
from pathlib import Path
from typing import Any

import pytest

from agent.clients.ghostfolio_client import GhostfolioClientError
from agent.clients.mock_client import MockGhostfolioClient
from agent.tools.transaction_categorizer import categorize_transactions

EXPECTED_ACTIVITY_TYPES = ("BUY", "SELL", "DIVIDEND", "FEE", "INTEREST", "LIABILITY")


class SpyOrdersClient:
    def __init__(self) -> None:
        self.call_count = 0

    async def get_orders(self, date_range: str | None = None) -> dict[str, Any]:
        self.call_count += 1
        return {"activities": [], "count": 0}


class ErroringOrdersClient:
    def __init__(self, error: Exception) -> None:
        self.call_count = 0
        self.error = error

    async def get_orders(self, date_range: str | None = None) -> dict[str, Any]:
        self.call_count += 1
        raise self.error


def _load_fixture_payload(fixture_path: Path) -> dict[str, Any]:
    with fixture_path.open("r", encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)

    assert isinstance(payload, dict)
    return payload


@pytest.mark.asyncio
async def test_categorize_transactions_happy_path_includes_all_activity_types(
    fixtures_dir: Path,
) -> None:
    orders_payload = _load_fixture_payload(fixtures_dir / "orders_mixed_types.json")
    mock_client = MockGhostfolioClient(orders=orders_payload)

    result = await categorize_transactions(mock_client, date_range="ytd")

    assert result.success is True
    assert result.error is None
    assert result.data is not None
    assert result.metadata["source"] == "transaction_categorizer"
    assert result.metadata["date_range"] == "ytd"

    by_type = result.data["by_type"]
    by_type_counts = result.data["by_type_counts"]
    summary = result.data["summary"]

    assert result.data["total_transactions"] == 6
    assert result.data["reported_count"] == 6
    assert set(by_type.keys()) == set(EXPECTED_ACTIVITY_TYPES)
    assert set(by_type_counts.keys()) == set(EXPECTED_ACTIVITY_TYPES)
    assert by_type_counts == {
        "BUY": 1,
        "SELL": 1,
        "DIVIDEND": 1,
        "FEE": 1,
        "INTEREST": 1,
        "LIABILITY": 1,
    }
    assert len(by_type["BUY"]) == 1
    assert len(by_type["SELL"]) == 1
    assert len(by_type["DIVIDEND"]) == 1
    assert len(by_type["FEE"]) == 1
    assert len(by_type["INTEREST"]) == 1
    assert len(by_type["LIABILITY"]) == 1
    assert summary["buy_total"] == pytest.approx(1000.0)
    assert summary["sell_total"] == pytest.approx(600.0)
    assert summary["dividend_total"] == pytest.approx(45.0)
    assert summary["interest_total"] == pytest.approx(7.5)
    assert summary["fee_total"] == pytest.approx(4.0)
    assert summary["liability_total"] == pytest.approx(300.0)


@pytest.mark.asyncio
async def test_categorize_transactions_invalid_period_short_circuits_api_call() -> None:
    spy_client = SpyOrdersClient()

    result = await categorize_transactions(spy_client, date_range="monthly")

    assert result.success is False
    assert result.data is None
    assert result.error == "INVALID_TIME_PERIOD"
    assert result.metadata["date_range"] == "monthly"
    assert spy_client.call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_code", "status"),
    [("API_TIMEOUT", None), ("API_ERROR", 500), ("AUTH_FAILED", 401)],
)
async def test_categorize_transactions_maps_client_error_codes(
    error_code: str, status: int | None
) -> None:
    failing_client = ErroringOrdersClient(
        GhostfolioClientError(error_code, status=status, detail="internal detail")
    )

    result = await categorize_transactions(failing_client, date_range="max")

    assert result.success is False
    assert result.data is None
    assert result.error == error_code
    assert result.metadata["date_range"] == "max"
    if status is None:
        assert "status" not in result.metadata
    else:
        assert result.metadata["status"] == status
    assert "internal detail" not in str(result.metadata)


@pytest.mark.asyncio
async def test_categorize_transactions_empty_activities_returns_zeroed_summary() -> None:
    mock_client = MockGhostfolioClient(orders={"activities": [], "count": 0})

    result = await categorize_transactions(mock_client, date_range="max")

    assert result.success is True
    assert result.error is None
    assert result.data is not None
    assert result.data["total_transactions"] == 0
    assert result.data["reported_count"] == 0
    assert result.data["by_type_counts"] == {
        "BUY": 0,
        "SELL": 0,
        "DIVIDEND": 0,
        "FEE": 0,
        "INTEREST": 0,
        "LIABILITY": 0,
    }
    assert result.data["by_type"] == {
        "BUY": [],
        "SELL": [],
        "DIVIDEND": [],
        "FEE": [],
        "INTEREST": [],
        "LIABILITY": [],
    }
    assert result.data["summary"] == {
        "buy_total": 0.0,
        "sell_total": 0.0,
        "dividend_total": 0.0,
        "interest_total": 0.0,
        "fee_total": 0.0,
        "liability_total": 0.0,
    }


@pytest.mark.asyncio
async def test_categorize_transactions_maps_unexpected_exceptions_to_api_error() -> None:
    failing_client = ErroringOrdersClient(RuntimeError("unexpected low-level detail"))

    result = await categorize_transactions(failing_client, date_range="max")

    assert result.success is False
    assert result.data is None
    assert result.error == "API_ERROR"
    assert result.metadata["date_range"] == "max"
    assert "unexpected low-level detail" not in str(result.metadata)
