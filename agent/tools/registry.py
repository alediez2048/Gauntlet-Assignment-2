"""Central tool registry with formal definitions and OpenAI function-calling schemas.

Each tool is registered as a ToolDefinition that bundles:
- The async callable (execution logic)
- A Pydantic input schema (validation + JSON schema generation)
- Metadata (name, description, route mapping)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel

from agent.tools.allocation_advisor import advise_asset_allocation
from agent.tools.base import ToolResult
from agent.tools.compliance_checker import check_compliance
from agent.tools.market_data import get_market_data
from agent.tools.portfolio_analyzer import analyze_portfolio_performance
from agent.tools.schemas import (
    AllocationAdvisorInput,
    ComplianceCheckInput,
    MarketDataInput,
    PortfolioAnalysisInput,
    TaxEstimateInput,
    TransactionCategorizeInput,
)
from agent.tools.tax_estimator import estimate_capital_gains_tax
from agent.tools.transaction_categorizer import categorize_transactions


@dataclass(frozen=True)
class ToolDefinition:
    """Formal tool definition used for routing, validation, and execution."""

    name: str
    description: str
    route: str
    input_schema: type[BaseModel]
    callable: Callable[..., Awaitable[ToolResult]]


TOOL_REGISTRY: Final[dict[str, ToolDefinition]] = {
    "analyze_portfolio_performance": ToolDefinition(
        name="analyze_portfolio_performance",
        description="Analyze portfolio returns and performance for a specific date range.",
        route="portfolio",
        input_schema=PortfolioAnalysisInput,
        callable=analyze_portfolio_performance,
    ),
    "categorize_transactions": ToolDefinition(
        name="categorize_transactions",
        description="Retrieve and group transactions by type (BUY/SELL/DIVIDEND/FEE/INTEREST/LIABILITY).",
        route="transactions",
        input_schema=TransactionCategorizeInput,
        callable=categorize_transactions,
    ),
    "estimate_capital_gains_tax": ToolDefinition(
        name="estimate_capital_gains_tax",
        description="Estimate capital gains tax liability using FIFO lot matching.",
        route="tax",
        input_schema=TaxEstimateInput,
        callable=estimate_capital_gains_tax,
    ),
    "advise_asset_allocation": ToolDefinition(
        name="advise_asset_allocation",
        description="Compare current allocation against a target profile and suggest rebalancing.",
        route="allocation",
        input_schema=AllocationAdvisorInput,
        callable=advise_asset_allocation,
    ),
    "check_compliance": ToolDefinition(
        name="check_compliance",
        description="Screen portfolio for regulatory red flags (wash sales, pattern day trading, concentration risk).",
        route="compliance",
        input_schema=ComplianceCheckInput,
        callable=check_compliance,
    ),
    "get_market_data": ToolDefinition(
        name="get_market_data",
        description="Fetch current prices and market metrics for portfolio holdings.",
        route="market",
        input_schema=MarketDataInput,
        callable=get_market_data,
    ),
}

# Reverse mapping: route name -> tool name (used by keyword router fallback)
ROUTE_TO_TOOL: Final[dict[str, str]] = {
    defn.route: defn.name for defn in TOOL_REGISTRY.values()
}


def build_openai_function_schemas() -> list[dict[str, Any]]:
    """Convert TOOL_REGISTRY into OpenAI function-calling tool definitions.

    Returns a list suitable for the ``tools`` parameter of ChatOpenAI.bind_tools()
    or the raw OpenAI API ``tools`` field.
    """
    tools: list[dict[str, Any]] = []
    for defn in TOOL_REGISTRY.values():
        json_schema = defn.input_schema.model_json_schema()
        # Remove Pydantic metadata keys that OpenAI doesn't expect
        json_schema.pop("title", None)
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": defn.name,
                    "description": defn.description,
                    "parameters": json_schema,
                },
            }
        )
    return tools
