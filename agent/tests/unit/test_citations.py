"""Unit tests for _build_citations and _compute_confidence."""

from __future__ import annotations

from agent.graph.nodes import _build_citations, _compute_confidence


# ---------- _build_citations ----------


class TestBuildCitations:
    def test_empty_history_returns_empty_list(self):
        assert _build_citations([]) == []

    def test_skips_failed_records(self):
        history = [
            {"tool_name": "analyze_portfolio_performance", "success": False, "data": None},
        ]
        assert _build_citations(history) == []

    def test_skips_records_with_no_data(self):
        history = [
            {"tool_name": "analyze_portfolio_performance", "success": True, "data": None},
        ]
        assert _build_citations(history) == []

    def test_portfolio_extracts_up_to_three_points(self):
        history = [
            {
                "tool_name": "analyze_portfolio_performance",
                "success": True,
                "data": {
                    "performance": {
                        "netPerformancePercentage": 5.23,
                        "totalInvestment": 10000.0,
                        "currentValue": 10523.0,
                    }
                },
            }
        ]
        citations = _build_citations(history)
        assert len(citations) == 3
        assert citations[0]["label"] == "[1]"
        assert citations[0]["display_name"] == "Portfolio Analysis"
        assert citations[0]["value"] == "5.23%"
        assert citations[1]["label"] == "[2]"
        assert citations[1]["value"] == "$10,000.00"
        assert citations[2]["label"] == "[3]"
        assert citations[2]["value"] == "$10,523.00"

    def test_transactions_extracts_total_and_top_category(self):
        history = [
            {
                "tool_name": "categorize_transactions",
                "success": True,
                "data": {
                    "total_transactions": 42,
                    "categories": {"BUY": 30, "SELL": 10, "DIVIDEND": 2},
                },
            }
        ]
        citations = _build_citations(history)
        assert len(citations) == 2
        assert citations[0]["value"] == "42"
        assert citations[1]["field"] == "categories.top"
        assert "BUY" in citations[1]["value"]

    def test_tax_extracts_liability_and_year(self):
        history = [
            {
                "tool_name": "estimate_capital_gains_tax",
                "success": True,
                "data": {"combined_liability": 1234.56, "tax_year": 2025},
            }
        ]
        citations = _build_citations(history)
        assert len(citations) == 2
        assert citations[0]["value"] == "$1,234.56"
        assert citations[1]["value"] == "2025"

    def test_compliance_extracts_violations_and_warnings(self):
        history = [
            {
                "tool_name": "check_compliance",
                "success": True,
                "data": {"total_violations": 1, "total_warnings": 3},
            }
        ]
        citations = _build_citations(history)
        assert len(citations) == 2
        assert citations[0]["value"] == "1"
        assert citations[1]["value"] == "3"

    def test_market_data_extracts_holdings_and_value(self):
        history = [
            {
                "tool_name": "get_market_data",
                "success": True,
                "data": {"total_holdings": 5, "total_market_value": 50000.0},
            }
        ]
        citations = _build_citations(history)
        assert len(citations) == 2
        assert citations[0]["value"] == "5"
        assert citations[1]["value"] == "$50,000.00"

    def test_allocation_extracts_top_asset_and_profile(self):
        history = [
            {
                "tool_name": "advise_asset_allocation",
                "success": True,
                "data": {
                    "current_allocation": {"AAPL": 45.0, "GOOGL": 30.0, "MSFT": 25.0},
                    "target_profile": "balanced",
                },
            }
        ]
        citations = _build_citations(history)
        assert len(citations) == 2
        assert "AAPL" in citations[0]["value"]
        assert citations[1]["value"] == "balanced"

    def test_multi_tool_labels_are_sequential(self):
        history = [
            {
                "tool_name": "check_compliance",
                "success": True,
                "data": {"total_violations": 0, "total_warnings": 1},
            },
            {
                "tool_name": "get_market_data",
                "success": True,
                "data": {"total_holdings": 3, "total_market_value": 25000.0},
            },
        ]
        citations = _build_citations(history)
        labels = [c["label"] for c in citations]
        assert labels == ["[1]", "[2]", "[3]", "[4]"]


# ---------- _compute_confidence ----------


class TestComputeConfidence:
    def test_empty_history_returns_zero(self):
        assert _compute_confidence([], 0) == 0.0

    def test_all_success_with_data_returns_high(self):
        history = [
            {"success": True, "data": {"key": "value"}},
        ]
        score = _compute_confidence(history, 1)
        assert score >= 0.95

    def test_single_failure_reduces_score(self):
        history = [
            {"success": True, "data": {"key": "value"}},
            {"success": False, "data": None},
        ]
        score = _compute_confidence(history, 2)
        # avg of (1.0, 0.6) = 0.8
        assert 0.5 <= score <= 0.85

    def test_all_failures_gives_low_score(self):
        history = [
            {"success": False, "data": None},
            {"success": False, "data": None},
        ]
        score = _compute_confidence(history, 2)
        assert score <= 0.6

    def test_retry_penalty_applied(self):
        history = [
            {"success": True, "data": {"key": "value"}},
        ]
        score_no_retry = _compute_confidence(history, 1)
        # step_count > len(history) triggers retry penalty
        score_with_retry = _compute_confidence(history, 3)
        assert score_with_retry < score_no_retry

    def test_empty_data_reduces_score(self):
        history = [
            {"success": True, "data": {}},
        ]
        score = _compute_confidence(history, 1)
        assert score < 1.0

    def test_score_clamped_to_zero_one(self):
        # Many failures should still clamp to 0.0
        history = [
            {"success": False, "data": None},
            {"success": False, "data": None},
            {"success": False, "data": None},
        ]
        score = _compute_confidence(history, 10)
        assert 0.0 <= score <= 1.0

    def test_mixed_results_intermediate_score(self):
        history = [
            {"success": True, "data": {"perf": 1.0}},
            {"success": True, "data": {"txns": 5}},
            {"success": False, "data": None},
        ]
        score = _compute_confidence(history, 3)
        # avg of (1.0, 1.0, 0.6) = 0.87
        assert 0.6 <= score <= 0.9
