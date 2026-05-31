"""Tests for Peter Lynch's six-category classifier. We pin the category each
fixture lands in and the shape of the verdict, not the prose."""

from __future__ import annotations

from app.services.lynch import classify_lynch

REQUIRED_KEYS = {"category", "rationale", "yardstick", "verdict", "metrics"}


def _quote(**overrides):
    base = {
        "sector": "Technology", "trailingEps": 5.0, "marketCap": 50e9,
        "revenueGrowth": 0.10, "earningsGrowth": 0.10,
        "dividendYield": 0.0, "pegRatio": 1.5,
    }
    base.update(overrides)
    return base


def test_shape_has_required_keys():
    out = classify_lynch(_quote())
    assert REQUIRED_KEYS <= set(out)
    assert isinstance(out["metrics"], dict)


def test_turnaround_when_earnings_negative():
    out = classify_lynch(_quote(trailingEps=-2.0))
    assert out["category"] == "Turnaround"


def test_fast_grower_on_high_growth():
    out = classify_lynch(_quote(earningsGrowth=0.30, pegRatio=0.8, marketCap=8e9))
    assert out["category"] == "Fast Grower"
    assert out["metrics"].get("peg") == 0.8


def test_stalwart_large_cap_moderate_growth():
    out = classify_lynch(_quote(earningsGrowth=0.11, marketCap=200e9, sector="Consumer Defensive"))
    assert out["category"] == "Stalwart"


def test_slow_grower_low_growth_high_yield():
    out = classify_lynch(_quote(earningsGrowth=0.02, dividendYield=0.05, marketCap=120e9,
                                sector="Utilities"))
    assert out["category"] == "Slow Grower"


def test_cyclical_sector_overrides_growth_buckets():
    out = classify_lynch(_quote(sector="Energy", earningsGrowth=0.12, marketCap=120e9))
    assert out["category"] == "Cyclical"


def test_asset_play_on_large_net_cash():
    # Net cash (cash − debt) is a big fraction of market cap → hidden asset value.
    data = {
        "balanceSheet": {
            "2024-12-31": {
                "Cash And Cash Equivalents": 40e9,
                "Total Debt": 2e9,
            },
        },
    }
    out = classify_lynch(_quote(marketCap=60e9, earningsGrowth=0.04, sector="Technology"), data)
    assert out["category"] == "Asset Play"


def test_fast_grower_verdict_flags_expensive_peg():
    cheap = classify_lynch(_quote(earningsGrowth=0.30, pegRatio=0.7, marketCap=8e9))
    rich  = classify_lynch(_quote(earningsGrowth=0.30, pegRatio=3.0, marketCap=8e9))
    assert "PEG" in cheap["verdict"] and "PEG" in rich["verdict"]
    assert cheap["verdict"] != rich["verdict"]
