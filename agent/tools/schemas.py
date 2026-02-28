"""Pydantic input schemas for all agent tools.

These models serve two purposes:
1. Validation/coercion of tool arguments before execution
2. Generation of OpenAI function-calling JSON schemas for the LLM router
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PortfolioAnalysisInput(BaseModel):
    """Analyze portfolio returns and performance for a specific date range."""

    time_period: Literal["1d", "wtd", "mtd", "ytd", "1y", "5y", "max"] = Field(
        default="ytd",
        description="Date range for performance calculation. Defaults to year-to-date.",
    )


class TransactionCategorizeInput(BaseModel):
    """Retrieve and group transactions by type (BUY/SELL/DIVIDEND/FEE/INTEREST/LIABILITY)."""

    date_range: Literal["1d", "wtd", "mtd", "ytd", "1y", "5y", "max"] = Field(
        default="max",
        description="Date range filter for transactions. Defaults to all-time.",
    )


class TaxEstimateInput(BaseModel):
    """Estimate capital gains tax liability using FIFO lot matching."""

    tax_year: int = Field(
        default_factory=lambda: datetime.now().year,
        ge=2020,
        le=datetime.now().year,
        description="Tax year to estimate (2020 to current year).",
    )
    income_bracket: Literal["low", "middle", "high"] = Field(
        default="middle",
        description="Income bracket for tax rate lookup: low (22%/0%), middle (24%/15%), high (24%/20%).",
    )


class AllocationAdvisorInput(BaseModel):
    """Compare current allocation against a target profile and suggest rebalancing."""

    target_profile: Literal["conservative", "balanced", "aggressive"] = Field(
        default="balanced",
        description="Risk profile to compare against.",
    )


class ComplianceCheckInput(BaseModel):
    """Screen portfolio for regulatory red flags (wash sales, pattern day trading, concentration risk)."""

    check_type: Literal["all", "wash_sale", "pattern_day_trading", "concentration"] = Field(
        default="all",
        description="Type of compliance check to run. 'all' runs every check.",
    )


class MarketDataInput(BaseModel):
    """Fetch current prices and market metrics for portfolio holdings."""

    symbols: list[str] | None = Field(
        default=None,
        description="Specific ticker symbols to fetch (e.g. ['AAPL', 'SPY']). Omit or null for all holdings.",
    )
    metrics: list[str] = Field(
        default=["price", "change", "change_percent", "currency", "market_value"],
        description="Data points to return. Options: price, change, change_percent, currency, market_value, quantity, all.",
    )


class PredictionMarketInput(BaseModel):
    """Browse, search, or analyze Polymarket prediction markets and manage positions."""

    action: Literal["browse", "search", "analyze", "positions"] = Field(
        default="browse",
        description="Action to perform: browse active markets, search by query, analyze a specific market, or view positions.",
    )
    query: str | None = Field(
        default=None,
        description="Search query for filtering markets (used with 'search' action).",
    )
    category: str | None = Field(
        default=None,
        description="Category filter (e.g. 'Crypto', 'Politics', 'Economics').",
    )
    market_slug: str | None = Field(
        default=None,
        description="Specific market slug for the 'analyze' action.",
    )
