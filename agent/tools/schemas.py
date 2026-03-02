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
    """Browse, search, analyze, simulate, compare, or model what-if portfolio reallocation scenarios on Polymarket prediction markets."""

    action: Literal["browse", "search", "analyze", "positions", "simulate", "trending", "compare", "scenario"] = Field(
        default="browse",
        description=(
            "Action to perform. Use 'scenario' when the user asks what-if questions about reallocating "
            "their portfolio into a prediction market (e.g. 'what if I bet my portfolio on X', "
            "'how would my portfolio perform if I went all-in on Y'). "
            "Use 'simulate' for a specific dollar bet simulation. "
            "Use 'search' to find markets by keyword. "
            "Use 'trending' for popular/active markets. "
            "Use 'analyze' for deep analysis of one market. "
            "Use 'browse' to list markets. "
            "Use 'positions' to view current holdings. "
            "Use 'compare' to compare 2-3 markets side by side."
        ),
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
        description="Specific market slug for analyze, simulate, or scenario actions.",
    )
    amount: float | None = Field(
        default=None,
        description="Dollar amount for the simulate action.",
    )
    outcome: str | None = Field(
        default=None,
        description="Outcome side: 'Yes' or 'No' (used with simulate and scenario).",
    )
    market_slugs: list[str] | None = Field(
        default=None,
        description="List of 2-3 market slugs for the compare action.",
    )
    allocation_mode: Literal["fixed", "percent", "all_in"] | None = Field(
        default=None,
        description="Allocation mode for scenario: fixed dollar amount, percentage of portfolio, or all-in.",
    )
    allocation_value: float | None = Field(
        default=None,
        description="Dollar amount or percentage value for the scenario action (depends on allocation_mode).",
    )
    time_horizon: Literal["1m", "3m", "6m", "1y"] | None = Field(
        default=None,
        description="Time horizon for scenario action. Defaults to 6 months.",
    )
    income_bracket: Literal["low", "middle", "high"] | None = Field(
        default=None,
        description="Income bracket for scenario tax estimation. Defaults to 'middle'.",
    )
