"""Pure computation helpers for prediction market analysis.

All functions are stateless and side-effect-free — safe to call
without mocks in unit tests.
"""

from __future__ import annotations

from typing import Any, Final

from agent.tools.allocation_advisor import _ASSET_CLASSES, _TARGET_ALLOCATIONS
from agent.tools.compliance_checker import _CONCENTRATION_THRESHOLD_PCT
from agent.tools.tax_estimator import _TAX_RATES_BY_BRACKET

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_KELLY_MAX_FRACTION: Final[float] = 0.25

_LIQUIDITY_GRADE_THRESHOLDS: Final[list[tuple[str, float, float]]] = [
    # (grade, min_volume, max_spread_pct)
    ("A", 500_000, 2.0),
    ("B", 100_000, 5.0),
    ("C", 50_000, 10.0),
    ("D", 10_000, 20.0),
]

_RISK_THRESHOLDS: Final[dict[str, float]] = {
    "low": 5.0,
    "moderate": 15.0,
}

_SCENARIO_DISCLAIMER: Final[str] = (
    "Hypothetical scenario for informational purposes only. "
    "Not financial, tax, or legal advice. "
    "Consult a qualified professional before making investment decisions."
)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def implied_probability(price: float) -> float:
    """Convert a market price (0–1) to an implied probability percentage."""
    clamped = max(0.001, min(0.999, float(price)))
    return round(clamped * 100, 2)


def kelly_fraction(prob: float, odds: float, bankroll: float) -> dict[str, Any]:
    """Compute the Kelly criterion bet fraction (capped).

    Returns:
        {"fraction": float, "amount": float, "capped": bool,
         "note": str}
    """
    if odds <= 0 or prob <= 0 or prob >= 1 or bankroll <= 0:
        return {
            "fraction": 0.0,
            "amount": 0.0,
            "capped": False,
            "note": "Informational hint only — not a recommendation.",
        }

    f = (prob * (odds + 1) - 1) / odds
    if f <= 0:
        return {
            "fraction": 0.0,
            "amount": 0.0,
            "capped": False,
            "note": "Informational hint only — not a recommendation.",
        }

    capped = f > _KELLY_MAX_FRACTION
    f = min(f, _KELLY_MAX_FRACTION)
    return {
        "fraction": round(f, 4),
        "amount": round(f * bankroll, 2),
        "capped": capped,
        "note": "Informational hint only — not a recommendation.",
    }


def expected_value(prob: float, payout: float, cost: float) -> dict[str, Any]:
    """Compute expected value of a binary bet.

    Returns:
        {"ev": float, "ev_pct": float, "profitable": bool}
    """
    if cost <= 0:
        return {"ev": 0.0, "ev_pct": 0.0, "profitable": False}

    ev = (prob * payout) - ((1 - prob) * cost)
    ev_pct = (ev / cost) * 100
    return {
        "ev": round(ev, 2),
        "ev_pct": round(ev_pct, 2),
        "profitable": ev > 0,
    }


def market_efficiency_score(
    bid: float, ask: float, volume: float
) -> dict[str, Any]:
    """Compute spread-based market efficiency metrics.

    Returns:
        {"spread": float, "spread_pct": float, "midpoint": float,
         "liquidity_grade": str, "efficiency_rating": str}
    """
    spread = round(ask - bid, 4)
    midpoint = (bid + ask) / 2
    spread_pct = round((spread / midpoint) * 100, 2) if midpoint > 0 else 0.0
    grade = _liquidity_grade(volume, spread_pct)
    rating = "efficient" if grade in ("A", "B") else ("moderate" if grade == "C" else "inefficient")
    return {
        "spread": spread,
        "spread_pct": spread_pct,
        "midpoint": round(midpoint, 4),
        "liquidity_grade": grade,
        "efficiency_rating": rating,
    }


def _liquidity_grade(volume: float, spread_pct: float) -> str:
    for grade, min_vol, max_spread in _LIQUIDITY_GRADE_THRESHOLDS:
        if volume >= min_vol and spread_pct <= max_spread:
            return grade
    return "F"


def portfolio_exposure_pct(position_value: float, net_worth: float) -> float:
    """What percentage of net worth does this position represent?"""
    if net_worth <= 0:
        return 0.0
    return round((position_value / net_worth) * 100, 2)


# ---------------------------------------------------------------------------
# Market formatting
# ---------------------------------------------------------------------------


def format_market_summary(market: dict[str, Any]) -> dict[str, Any]:
    """Standardize a raw Gamma API market dict into our display format.

    Adds implied_probabilities, spread info, and liquidity_grade.
    """
    import json as _json

    prices = market.get("outcomePrices", "[]")
    if isinstance(prices, str):
        try:
            prices = _json.loads(prices)
        except (ValueError, TypeError):
            prices = []

    outcomes = market.get("outcomes", [])
    outcome_display: list[dict[str, Any]] = []
    implied_probs: list[float] = []
    for i, outcome in enumerate(outcomes):
        price = float(prices[i]) if i < len(prices) else 0.0
        outcome_display.append({"label": outcome, "price": price})
        implied_probs.append(implied_probability(price))

    bid = float(market.get("bestBid") or 0)
    ask = float(market.get("bestAsk") or 0)
    volume = float(market.get("volume24hr") or 0)

    efficiency = market_efficiency_score(bid, ask, volume) if bid > 0 and ask > 0 else None

    result: dict[str, Any] = {
        "question": market.get("question", "Unknown"),
        "slug": market.get("slug", ""),
        "outcomes": outcome_display,
        "volume_24h": volume,
        "category": market.get("category", ""),
        "end_date": market.get("endDate", ""),
        "active": market.get("active", False),
        "implied_probabilities": implied_probs,
        "liquidity_grade": efficiency["liquidity_grade"] if efficiency else "N/A",
    }

    if efficiency:
        result["spread_pct"] = efficiency["spread_pct"]

    return result


# ---------------------------------------------------------------------------
# Scenario computation
# ---------------------------------------------------------------------------


def risk_level(concentration_pct: float) -> str:
    """Classify risk based on portfolio concentration percentage."""
    if concentration_pct < _RISK_THRESHOLDS["low"]:
        return "low"
    if concentration_pct <= _RISK_THRESHOLDS["moderate"]:
        return "moderate"
    return "high"


def pro_rata_liquidation(
    holdings: list[dict[str, Any]], amount: float
) -> list[dict[str, Any]]:
    """Compute proportional liquidation across holdings.

    Args:
        holdings: List of holding dicts with 'symbol', 'valueInBaseCurrency', 'investment'.
        amount: Total dollar amount to liquidate.

    Returns:
        List of per-holding liquidation dicts with gain/loss.
    """
    total_value = sum(float(h.get("valueInBaseCurrency", 0)) for h in holdings)
    if total_value <= 0:
        return []

    liquidations: list[dict[str, Any]] = []
    for h in holdings:
        h_value = float(h.get("valueInBaseCurrency", 0))
        h_investment = float(h.get("investment", 0))
        if h_value <= 0:
            continue

        liquidated_value = h_value * (amount / total_value)
        # Proportional cost basis
        cost_basis = h_investment * (liquidated_value / h_value) if h_value > 0 else 0
        gain = liquidated_value - cost_basis

        liquidations.append({
            "symbol": h.get("symbol", "UNKNOWN"),
            "liquidated_value": round(liquidated_value, 2),
            "cost_basis": round(cost_basis, 2),
            "gain": round(gain, 2),
        })

    return liquidations


def compute_scenario(
    net_worth: float,
    holdings: list[dict[str, Any]],
    market: dict[str, Any],
    allocation_mode: str,
    allocation_value: float,
    outcome_price: float,
    income_bracket: str = "middle",
    target_profile: str = "balanced",
) -> dict[str, Any]:
    """Compute a full reallocation scenario.

    Returns the complete scenario response dict per the output contract.
    """
    import json as _json

    # --- Resolve allocation amount ---
    if allocation_mode == "percent":
        resolved_amount = net_worth * (allocation_value / 100)
    elif allocation_mode == "all_in":
        resolved_amount = net_worth
    else:  # fixed
        resolved_amount = allocation_value

    resolved_amount = min(resolved_amount, net_worth)
    resolved_amount = round(resolved_amount, 2)

    # --- Market info ---
    prices = market.get("outcomePrices", "[]")
    if isinstance(prices, str):
        try:
            prices = _json.loads(prices)
        except (ValueError, TypeError):
            prices = []

    imp_prob = implied_probability(outcome_price)

    # --- Shares & payouts (binary market) ---
    shares = resolved_amount / outcome_price if outcome_price > 0 else 0
    win_payout = round(shares * 1.0, 2)  # binary: $1/share on win
    win_net_gain = round(win_payout - resolved_amount, 2)
    lose_payout = 0.0
    lose_net_loss = round(-resolved_amount, 2)

    # --- Post-trade net worth ---
    post_trade_net_worth = net_worth  # No value change at trade time
    portfolio_value_ex_prediction = round(net_worth - resolved_amount, 2)

    win_post_outcome_nw = round(portfolio_value_ex_prediction + win_payout, 2)
    win_return_pct = round((win_net_gain / net_worth) * 100, 2) if net_worth > 0 else 0

    lose_post_outcome_nw = round(portfolio_value_ex_prediction + lose_payout, 2)
    lose_return_pct = round((lose_net_loss / net_worth) * 100, 2) if net_worth > 0 else 0

    # --- EV & Kelly ---
    prob = outcome_price  # Price IS the implied probability
    odds = (1.0 / outcome_price - 1) if outcome_price > 0 and outcome_price < 1 else 0
    ev_result = expected_value(prob, 1.0, outcome_price)
    kelly_result = kelly_fraction(prob, odds, net_worth)

    break_even_prob = round(outcome_price * 100, 2)

    # --- Baseline allocation ---
    baseline_by_class: dict[str, float] = {ac: 0.0 for ac in _ASSET_CLASSES}
    total_holding_value = sum(float(h.get("valueInBaseCurrency", 0)) for h in holdings)

    for h in holdings:
        ac = h.get("assetClass", "EQUITY")
        h_val = float(h.get("valueInBaseCurrency", 0))
        if net_worth > 0:
            baseline_by_class[ac] = baseline_by_class.get(ac, 0) + round((h_val / net_worth) * 100, 2)

    top_holdings = []
    for h in sorted(holdings, key=lambda x: float(x.get("valueInBaseCurrency", 0)), reverse=True)[:5]:
        h_val = float(h.get("valueInBaseCurrency", 0))
        top_holdings.append({
            "symbol": h.get("symbol", "UNKNOWN"),
            "value": h_val,
            "weight_pct": round((h_val / net_worth) * 100, 2) if net_worth > 0 else 0,
        })

    # --- Post-trade allocation ---
    post_trade_by_class = dict(baseline_by_class)
    # Reduce equity (or whatever classes the holdings are) proportionally
    if net_worth > 0:
        for ac in post_trade_by_class:
            post_trade_by_class[ac] = round(
                post_trade_by_class[ac] * (1 - resolved_amount / net_worth), 2
            )
        # Add prediction market allocation
        post_trade_by_class["ALTERNATIVE_INVESTMENT"] = round(
            post_trade_by_class.get("ALTERNATIVE_INVESTMENT", 0) + (resolved_amount / net_worth) * 100, 2
        )

    # --- Allocation drift from target ---
    target_alloc = _TARGET_ALLOCATIONS.get(target_profile, _TARGET_ALLOCATIONS["balanced"])
    drift: dict[str, float] = {}
    for ac in _ASSET_CLASSES:
        post_val = post_trade_by_class.get(ac, 0)
        target_val = target_alloc.get(ac, 0)
        drift[ac] = round(abs(post_val - target_val), 2)

    # --- Concentration impact ---
    pre_trade_max_single = max(
        (round((float(h.get("valueInBaseCurrency", 0)) / net_worth) * 100, 2)
         for h in holdings),
        default=0,
    ) if net_worth > 0 else 0

    post_trade_prediction_pct = round((resolved_amount / net_worth) * 100, 2) if net_worth > 0 else 0

    # Post-trade max single = max(largest remaining holding %, prediction %)
    post_trade_max_single = max(
        pre_trade_max_single * (1 - resolved_amount / net_worth) if net_worth > 0 else 0,
        post_trade_prediction_pct,
    )
    post_trade_max_single = round(post_trade_max_single, 2)

    concentration_flag = post_trade_prediction_pct > _CONCENTRATION_THRESHOLD_PCT

    # --- Risk level ---
    r_level = risk_level(post_trade_prediction_pct)

    # --- Compliance flags ---
    compliance_flags: list[dict[str, str]] = []
    if concentration_flag:
        compliance_flags.append({
            "type": "CONCENTRATION_RISK",
            "description": f"Prediction market position would be {post_trade_prediction_pct}% of portfolio.",
        })

    risk_flags: list[str] = []
    if r_level == "high":
        risk_flags.append("HIGH_CONCENTRATION")

    # --- Tax estimates ---
    liquidations = pro_rata_liquidation(holdings, resolved_amount)
    total_liquidation_gains = sum(max(l["gain"], 0) for l in liquidations)

    # Determine holding period from dateOfFirstActivity
    from datetime import datetime

    holding_period = "short_term"
    if holdings:
        first_activity = holdings[0].get("dateOfFirstActivity", "")
        if isinstance(first_activity, str) and first_activity:
            try:
                first_date = datetime.strptime(first_activity[:10], "%Y-%m-%d")
                days_held = (datetime.now() - first_date).days
                if days_held > 365:
                    holding_period = "long_term"
            except (ValueError, TypeError):
                pass

    tax_rates = _TAX_RATES_BY_BRACKET.get(income_bracket, _TAX_RATES_BY_BRACKET["middle"])
    liquidation_rate = tax_rates[holding_period]
    liquidation_tax = round(max(total_liquidation_gains, 0) * liquidation_rate, 2)

    # Win-case tax (prediction gains are short-term)
    win_tax_rate = tax_rates["short_term"]
    win_case_tax = round(max(win_net_gain, 0) * win_tax_rate, 2)

    # Lose-case offset
    lose_offset = round(lose_net_loss * tax_rates["short_term"], 2)

    return {
        "action": "scenario",
        "market": {
            "question": market.get("question", "Unknown"),
            "slug": market.get("slug", ""),
            "outcome_side": "Yes",  # Default; caller can override
            "outcome_price": outcome_price,
            "implied_probability": imp_prob,
        },
        "allocation": {
            "mode": allocation_mode,
            "input_value": allocation_value,
            "resolved_amount": resolved_amount,
            "source": "pro-rata liquidation",
        },
        "baseline": {
            "net_worth": net_worth,
            "allocation_by_class": {k: v for k, v in baseline_by_class.items() if v > 0 or k in ("EQUITY", "ALTERNATIVE_INVESTMENT")},
            "top_holdings": top_holdings,
        },
        "scenario_metrics": {
            "post_trade_net_worth": post_trade_net_worth,
            "portfolio_value_ex_prediction": portfolio_value_ex_prediction,
            "prediction_position_value": resolved_amount,
            "win_case": {
                "payout": win_payout,
                "net_gain": win_net_gain,
                "post_outcome_net_worth": win_post_outcome_nw,
                "return_pct": win_return_pct,
            },
            "lose_case": {
                "payout": lose_payout,
                "net_loss": lose_net_loss,
                "post_outcome_net_worth": lose_post_outcome_nw,
                "return_pct": lose_return_pct,
            },
            "expected_value": ev_result,
            "break_even_probability": break_even_prob,
            "kelly_hint": kelly_result,
        },
        "risk_assessment": {
            "concentration_impact": {
                "pre_trade_max_single_pct": pre_trade_max_single,
                "post_trade_prediction_pct": post_trade_prediction_pct,
                "post_trade_max_single_pct": post_trade_max_single,
                "concentration_flag": concentration_flag,
            },
            "allocation_drift": {
                "pre_trade": {k: v for k, v in baseline_by_class.items() if v > 0 or k in ("EQUITY", "ALTERNATIVE_INVESTMENT")},
                "post_trade": {k: v for k, v in post_trade_by_class.items() if v > 0 or k in ("EQUITY", "ALTERNATIVE_INVESTMENT")},
                "drift_from_balanced": drift,
            },
            "risk_level": r_level,
            "flags": risk_flags,
        },
        "tax_estimate": {
            "income_bracket": income_bracket,
            "liquidation_tax": {
                "estimated_gains": total_liquidation_gains,
                "estimated_tax": liquidation_tax,
                "holding_period": holding_period,
                "rate_applied": liquidation_rate,
            },
            "win_case_tax": {
                "prediction_gain": win_net_gain,
                "holding_period": "short_term",
                "estimated_tax": win_case_tax,
                "rate_applied": win_tax_rate,
            },
            "lose_case_tax": {
                "prediction_loss": lose_net_loss,
                "tax_offset": lose_offset,
                "note": "Loss may offset other capital gains.",
            },
        },
        "compliance_flags": compliance_flags,
        "disclaimer": _SCENARIO_DISCLAIMER,
    }
