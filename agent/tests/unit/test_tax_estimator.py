import json
from pathlib import Path
from typing import Any

import pytest

from agent.clients.ghostfolio_client import GhostfolioClientError
from agent.clients.mock_client import MockGhostfolioClient
from agent.tools.tax_estimator import estimate_capital_gains_tax


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
async def test_estimate_capital_gains_tax_happy_path_matches_hand_verified_totals(
    fixtures_dir: Path,
) -> None:
    orders_payload = _load_fixture_payload(fixtures_dir / "orders_tax_scenarios.json")
    mock_client = MockGhostfolioClient(orders=orders_payload)

    result = await estimate_capital_gains_tax(
        mock_client,
        tax_year=2024,
        income_bracket="middle",
    )

    assert result.success is True
    assert result.error is None
    assert result.data is not None
    assert result.metadata["source"] == "capital_gains_tax_estimator"
    assert result.metadata["tax_year"] == 2024
    assert result.metadata["income_bracket"] == "middle"

    short_term = result.data["short_term"]
    long_term = result.data["long_term"]

    assert result.data["tax_year"] == 2024
    assert result.data["income_bracket"] == "middle"
    assert short_term["total_gains"] == pytest.approx(250.0)
    assert short_term["total_losses"] == pytest.approx(-150.0)
    assert short_term["net"] == pytest.approx(100.0)
    assert short_term["estimated_tax"] == pytest.approx(24.0)
    assert short_term["rate_applied"] == pytest.approx(0.24)
    assert long_term["total_gains"] == pytest.approx(200.0)
    assert long_term["total_losses"] == pytest.approx(0.0)
    assert long_term["net"] == pytest.approx(200.0)
    assert long_term["estimated_tax"] == pytest.approx(30.0)
    assert long_term["rate_applied"] == pytest.approx(0.15)
    assert result.data["combined_liability"] == pytest.approx(54.0)
    assert result.data["disclaimer"] == "Simplified estimate using FIFO. Not financial advice."
    assert len(result.data["per_asset"]) == 3


@pytest.mark.asyncio
async def test_estimate_capital_gains_tax_classifies_short_and_long_term_entries(
    fixtures_dir: Path,
) -> None:
    orders_payload = _load_fixture_payload(fixtures_dir / "orders_tax_scenarios.json")
    mock_client = MockGhostfolioClient(orders=orders_payload)

    result = await estimate_capital_gains_tax(
        mock_client,
        tax_year=2024,
        income_bracket="middle",
    )

    assert result.success is True
    assert result.data is not None

    per_asset = result.data["per_asset"]
    short_term_entries = [entry for entry in per_asset if entry["holding_period"] == "short_term"]
    long_term_entries = [entry for entry in per_asset if entry["holding_period"] == "long_term"]

    assert len(short_term_entries) == 2
    assert len(long_term_entries) == 1
    assert {entry["symbol"] for entry in short_term_entries} == {"AAPL", "TSLA"}
    assert long_term_entries[0]["symbol"] == "MSFT"


@pytest.mark.asyncio
async def test_estimate_capital_gains_tax_buys_only_returns_zero_liability() -> None:
    mock_client = MockGhostfolioClient(
        orders={
            "activities": [
                {
                    "type": "BUY",
                    "date": "2024-01-01T00:00:00.000Z",
                    "quantity": 10,
                    "unitPrice": 100,
                    "SymbolProfile": {"symbol": "AAPL"},
                }
            ],
            "count": 1,
        }
    )

    result = await estimate_capital_gains_tax(mock_client, tax_year=2024, income_bracket="high")

    assert result.success is True
    assert result.error is None
    assert result.data is not None
    assert result.data["combined_liability"] == pytest.approx(0.0)
    assert result.data["per_asset"] == []
    assert result.data["short_term"]["net"] == pytest.approx(0.0)
    assert result.data["short_term"]["estimated_tax"] == pytest.approx(0.0)
    assert result.data["long_term"]["net"] == pytest.approx(0.0)
    assert result.data["long_term"]["estimated_tax"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_estimate_capital_gains_tax_invalid_tax_year_short_circuits_api_call() -> None:
    spy_client = SpyOrdersClient()

    result = await estimate_capital_gains_tax(spy_client, tax_year=2019, income_bracket="middle")

    assert result.success is False
    assert result.data is None
    assert result.error == "INVALID_TAX_YEAR"
    assert result.metadata["tax_year"] == 2019
    assert spy_client.call_count == 0


@pytest.mark.asyncio
async def test_estimate_capital_gains_tax_invalid_income_bracket_short_circuits_api_call() -> None:
    spy_client = SpyOrdersClient()

    result = await estimate_capital_gains_tax(spy_client, tax_year=2024, income_bracket="vip")

    assert result.success is False
    assert result.data is None
    assert result.error == "INVALID_INCOME_BRACKET"
    assert result.metadata["income_bracket"] == "vip"
    assert spy_client.call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_code", "status"),
    [("API_TIMEOUT", None), ("API_ERROR", 500), ("AUTH_FAILED", 401)],
)
async def test_estimate_capital_gains_tax_maps_client_error_codes(
    error_code: str, status: int | None
) -> None:
    failing_client = ErroringOrdersClient(
        GhostfolioClientError(error_code, status=status, detail="internal detail")
    )

    result = await estimate_capital_gains_tax(
        failing_client,
        tax_year=2024,
        income_bracket="middle",
    )

    assert result.success is False
    assert result.data is None
    assert result.error == error_code
    assert result.metadata["tax_year"] == 2024
    assert result.metadata["income_bracket"] == "middle"
    if status is None:
        assert "status" not in result.metadata
    else:
        assert result.metadata["status"] == status
    assert "internal detail" not in str(result.metadata)


@pytest.mark.asyncio
async def test_estimate_capital_gains_tax_maps_unexpected_exceptions_to_api_error() -> None:
    failing_client = ErroringOrdersClient(RuntimeError("unexpected low-level detail"))

    result = await estimate_capital_gains_tax(
        failing_client,
        tax_year=2024,
        income_bracket="middle",
    )

    assert result.success is False
    assert result.data is None
    assert result.error == "API_ERROR"
    assert result.metadata["tax_year"] == 2024
    assert result.metadata["income_bracket"] == "middle"
    assert "unexpected low-level detail" not in str(result.metadata)


@pytest.mark.asyncio
async def test_estimate_capital_gains_tax_consumes_multiple_lots_for_single_sell() -> None:
    mock_client = MockGhostfolioClient(
        orders={
            "activities": [
                {
                    "type": "BUY",
                    "date": "2024-01-01T00:00:00.000Z",
                    "quantity": 5,
                    "unitPrice": 100,
                    "SymbolProfile": {"symbol": "NVDA"},
                },
                {
                    "type": "BUY",
                    "date": "2024-02-01T00:00:00.000Z",
                    "quantity": 5,
                    "unitPrice": 120,
                    "SymbolProfile": {"symbol": "NVDA"},
                },
                {
                    "type": "SELL",
                    "date": "2024-03-01T00:00:00.000Z",
                    "quantity": 8,
                    "unitPrice": 150,
                    "SymbolProfile": {"symbol": "NVDA"},
                },
            ],
            "count": 3,
        }
    )

    result = await estimate_capital_gains_tax(mock_client, tax_year=2024, income_bracket="middle")

    assert result.success is True
    assert result.error is None
    assert result.data is not None

    per_asset = result.data["per_asset"]
    assert len(per_asset) == 2
    assert per_asset[0] == {
        "symbol": "NVDA",
        "gain_loss": pytest.approx(250.0),
        "holding_period": "short_term",
        "cost_basis": pytest.approx(500.0),
        "proceeds": pytest.approx(750.0),
    }
    assert per_asset[1] == {
        "symbol": "NVDA",
        "gain_loss": pytest.approx(90.0),
        "holding_period": "short_term",
        "cost_basis": pytest.approx(360.0),
        "proceeds": pytest.approx(450.0),
    }
    assert result.data["short_term"]["total_gains"] == pytest.approx(340.0)
    assert result.data["short_term"]["net"] == pytest.approx(340.0)
    assert result.data["short_term"]["estimated_tax"] == pytest.approx(81.6)
