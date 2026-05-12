"""Tests for valuation primitives. Mostly None-path + monotonic-sanity checks.

The exact intrinsic-value numbers are not the point — sign, magnitude and
None-safety are. Anyone over-fitting these tests should refactor instead."""

from __future__ import annotations

import math

from app.services.valuation import (
    circle_of_competence_check,
    compute_roic,
    compute_valuation,
    dcf_intrinsic_value,
    earnings_power_value,
    fcf_yield_value,
    graham_number,
    margin_of_safety,
)


# ── graham_number ─────────────────────────────────────────────────────────────

def test_graham_number_basic():
    # sqrt(22.5 * 5 * 20) = sqrt(2250) ≈ 47.43
    assert graham_number(5.0, 20.0) == math.sqrt(22.5 * 5 * 20)


def test_graham_number_none_when_inputs_missing_or_negative():
    assert graham_number(None, 20.0) is None
    assert graham_number(5.0, None) is None
    assert graham_number(-1.0, 20.0) is None
    assert graham_number(5.0, 0.0) is None


# ── dcf ───────────────────────────────────────────────────────────────────────

def test_dcf_positive_for_healthy_inputs():
    iv = dcf_intrinsic_value(fcf=10e9, shares=1e9, growth_rate=0.08, discount_rate=0.10)
    assert iv is not None and iv > 0


def test_dcf_higher_growth_yields_higher_iv():
    low  = dcf_intrinsic_value(10e9, 1e9, growth_rate=0.03, discount_rate=0.10)
    high = dcf_intrinsic_value(10e9, 1e9, growth_rate=0.12, discount_rate=0.10)
    assert low is not None and high is not None and high > low


def test_dcf_none_when_discount_le_terminal():
    assert dcf_intrinsic_value(10e9, 1e9, terminal_growth=0.12, discount_rate=0.10) is None


def test_dcf_none_on_zero_or_negative_inputs():
    assert dcf_intrinsic_value(0, 1e9) is None
    assert dcf_intrinsic_value(10e9, 0) is None
    assert dcf_intrinsic_value(-1, 1e9) is None


# ── fcf_yield_value ───────────────────────────────────────────────────────────

def test_fcf_yield_value_basic():
    # FCF/share = 10 → at 7% required yield, fair value = 10/0.07 ≈ 142.86
    iv = fcf_yield_value(fcf=10e9, shares=1e9, required_yield=0.07)
    assert iv is not None
    assert math.isclose(iv, round(10 / 0.07, 2), rel_tol=1e-3)


def test_fcf_yield_value_none_on_zero_yield():
    assert fcf_yield_value(10e9, 1e9, required_yield=0) is None


# ── earnings_power_value ──────────────────────────────────────────────────────

def test_epv_basic():
    # NOPAT/share = 5; perpetuity at 10% → 50
    iv = earnings_power_value(nopat=5e9, shares=1e9, discount_rate=0.10)
    assert iv == 50.0


def test_epv_none_on_missing_inputs():
    assert earnings_power_value(None, 1e9) is None
    assert earnings_power_value(5e9, None) is None
    assert earnings_power_value(-1, 1e9) is None


# ── margin_of_safety ──────────────────────────────────────────────────────────

def test_mos_positive_when_iv_above_price():
    assert margin_of_safety(current_price=80, intrinsic_value=100) == 20.0


def test_mos_negative_when_price_above_iv():
    assert margin_of_safety(current_price=120, intrinsic_value=100) == -20.0


def test_mos_none_on_missing_inputs():
    assert margin_of_safety(None, 100) is None
    assert margin_of_safety(100, None) is None
    assert margin_of_safety(100, 0) is None


# ── ROIC ──────────────────────────────────────────────────────────────────────

def test_roic_happy_path():
    # NOPAT = 1e9 * (1 - 0.21) = 0.79e9; invested capital = assets - cash = 4e9 - 1e9 = 3e9
    r = compute_roic(
        op_income=1e9, tax_rate=0.21, total_debt=1e9,
        total_assets=4e9, cash=1e9,
    )
    assert r is not None and 0.20 < r < 0.30


def test_roic_none_on_negative_op_income():
    assert compute_roic(-1, 0.21, 1e9, 4e9, 1e9) is None


def test_roic_none_when_assets_missing():
    assert compute_roic(1e9, 0.21, None, None, 0) is None


# ── circle_of_competence ──────────────────────────────────────────────────────

def test_circle_of_competence_flags_financial_sector():
    out = circle_of_competence_check({"sector": "Financial Services", "trailingEps": 5})
    assert not out["within"]
    assert any("financial" in f.lower() for f in out["flags"])


def test_circle_of_competence_passes_clean_consumer_staple():
    out = circle_of_competence_check({
        "sector":       "Consumer Defensive",
        "trailingEps":  4.0,
        "freeCashflow": 1e9,
        "pegRatio":     1.5,
    })
    assert out["within"]
    assert out["complexity"] == "Low"


def test_circle_of_competence_flags_high_peg():
    out = circle_of_competence_check({"sector": "Tech", "pegRatio": 5.0})
    assert any("PEG" in f for f in out["flags"])


# ── compute_valuation end-to-end ──────────────────────────────────────────────

def _quote(**overrides):
    base = {
        "price":             150.0,
        "trailingEps":       6.0,
        "bookValue":         4.0,
        "freeCashflow":      100e9,
        "sharesOutstanding": 16e9,
        "marketCap":         2.4e12,
        "revenueGrowth":     0.08,
        "sector":            "Technology",
        "pegRatio":          1.5,
    }
    base.update(overrides)
    return base


def test_compute_valuation_returns_all_keys_without_financials():
    out = compute_valuation(_quote())
    for k in (
        "graham", "dcf_base", "fcf_yield_value", "epv",
        "current_price", "mos_graham", "mos_dcf", "mos_fcf_yield",
        "mos_epv", "roic", "price_to_fcf", "circle_of_competence", "inputs",
    ):
        assert k in out
    # No financials passed → EPV and ROIC should be None
    assert out["epv"] is None and out["roic"] is None


def test_compute_valuation_with_financials_populates_epv_and_roic():
    data = {
        "financials": {
            "2024-09-30": {
                "Operating Income": 120e9,
                "Tax Provision":    20e9,
                "Pretax Income":   100e9,
            },
        },
        "balanceSheet": {
            "2024-09-30": {
                "Total Debt":                 110e9,
                "Total Assets":               350e9,
                "Cash And Cash Equivalents":  30e9,
            },
        },
        "cashflow": {},
    }
    out = compute_valuation(_quote(), data)
    assert out["epv"] is not None and out["epv"] > 0
    assert out["roic"] is not None and out["roic"] > 0
