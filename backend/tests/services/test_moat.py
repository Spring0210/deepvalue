"""Moat classifier tests. The classifier is heuristic — we don't pin the
exact `primary_type` for every fixture (the weights might be tuned later).
We pin only what the agent prompt actually depends on:
 - strength bucket is one of {Wide, Narrow, None}
 - high-quality businesses get Wide; deeply-impaired ones get None
 - dict shape matches what the tool returns to the LLM"""

from __future__ import annotations

from app.services.moat import compute_moat


# ── shape ─────────────────────────────────────────────────────────────────────

def test_compute_moat_dict_shape():
    out = compute_moat({})
    assert set(out.keys()) == {"strength", "primary_type", "scores", "indicators"}
    assert out["strength"] in {"Wide", "Narrow", "None"}
    assert isinstance(out["scores"], dict)
    assert isinstance(out["indicators"], list)


def test_compute_moat_empty_quote_is_none_or_narrow():
    # No data → no real signal; classifier should not crash and not claim Wide.
    out = compute_moat({})
    assert out["strength"] in {"None", "Narrow"}


# ── happy paths ───────────────────────────────────────────────────────────────

def test_wide_moat_for_premium_tech_business():
    out = compute_moat({
        "sector":          "Technology",
        "grossMargins":    0.70,
        "operatingMargins":0.35,
        "roe":             0.50,
        "revenueGrowth":   0.20,
        "pe":              28.0,
        "marketCap":       2.5e12,
    })
    assert out["strength"] == "Wide"
    # All five moat types are scored
    assert set(out["scores"].keys()) == {
        "Network Effect", "Switching Costs", "Cost Advantage",
        "Intangible Assets", "Efficient Scale",
    }


def test_utility_is_efficient_scale_or_cost_advantage():
    out = compute_moat({
        "sector":         "Utilities",
        "grossMargins":   0.30,
        "operatingMargins": 0.18,
        "roe":            0.10,
        "revenueGrowth":  0.02,
        "dividendYield":  0.04,
        "marketCap":      80e9,
    })
    # Utility usually scores highest on Efficient Scale, but the test should
    # not pin the exact label — it's a soft heuristic.
    assert out["primary_type"] in {"Efficient Scale", "Cost Advantage", None}
    assert out["strength"] in {"Wide", "Narrow"}


def test_impaired_business_classified_as_none():
    out = compute_moat({
        "sector":           "Industrials",
        "grossMargins":     0.05,
        "operatingMargins": 0.01,
        "roe":              0.02,
        "revenueGrowth":   -0.05,
        "marketCap":        500e6,
    })
    assert out["strength"] == "None"


# ── scores numeric ────────────────────────────────────────────────────────────

def test_scores_in_unit_interval():
    out = compute_moat({
        "sector":         "Consumer Defensive",
        "grossMargins":   0.55, "operatingMargins": 0.20,
        "roe":            0.30, "revenueGrowth":    0.05,
        "pe":             24, "marketCap": 250e9,
    })
    for score in out["scores"].values():
        assert 0.0 <= score <= 1.0


# ── D: evidence-based strength (ROIC persistence + margin stability) ──────────

def _years(fin_row, bal_row, n=4):
    fin, bal = {}, {}
    for i in range(n):
        key = f"{2024 - i}-12-31"
        fin[key] = dict(fin_row)
        bal[key] = dict(bal_row)
    return {"financials": fin, "balanceSheet": bal, "cashflow": {}}


def test_pe_no_longer_inflates_moat_scores():
    # P/E is market sentiment, not moat evidence; it must not change scores.
    base = {
        "sector": "Consumer Defensive", "grossMargins": 0.55,
        "operatingMargins": 0.20, "roe": 0.30, "revenueGrowth": 0.05,
        "marketCap": 250e9,
    }
    assert compute_moat({**base, "pe": 8})["scores"] == compute_moat({**base, "pe": 40})["scores"]


def test_wide_on_persistent_high_roic_and_stable_margins():
    data = _years(
        {"Operating Income": 100.0, "Tax Provision": 21.0, "Pretax Income": 100.0,
         "Gross Profit": 60.0, "Total Revenue": 100.0},
        {"Total Debt": 0.0, "Common Stock Equity": 400.0, "Cash And Cash Equivalents": 0.0},
    )
    quote = {
        "sector": "Technology", "grossMargins": 0.60, "operatingMargins": 0.30,
        "roe": 0.20, "revenueGrowth": 0.10, "marketCap": 1e12,
    }
    out = compute_moat(quote, data)
    assert out["strength"] == "Wide"
    assert any("ROIC" in ind for ind in out["indicators"])


def test_none_when_roic_persistently_below_hurdle():
    data = _years(
        {"Operating Income": 5.0, "Tax Provision": 1.0, "Pretax Income": 5.0,
         "Gross Profit": 20.0, "Total Revenue": 100.0},
        {"Total Debt": 0.0, "Common Stock Equity": 400.0, "Cash And Cash Equivalents": 0.0},
    )
    quote = {
        "sector": "Industrials", "grossMargins": 0.20, "operatingMargins": 0.05,
        "roe": 0.02, "revenueGrowth": -0.05, "marketCap": 1e9,
    }
    out = compute_moat(quote, data)
    assert out["strength"] == "None"
