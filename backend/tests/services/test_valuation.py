"""Tests for valuation primitives. Mostly None-path + monotonic-sanity checks.

The exact intrinsic-value numbers are not the point — sign, magnitude and
None-safety are. Anyone over-fitting these tests should refactor instead."""

from __future__ import annotations

import math

from app.services.valuation import (
    capm_discount_rate,
    circle_of_competence_check,
    compute_roic,
    compute_valuation,
    dcf_intrinsic_value,
    dcf_valuation_range,
    earnings_power_value,
    fcf_yield_value,
    graham_number,
    margin_of_safety,
    reverse_dcf_growth,
    valuation_verdict,
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

def test_roic_uses_financing_invested_capital():
    # NOPAT = 1e9 * (1 - 0.21) = 0.79e9.
    # Invested Capital = debt + equity − cash = 1 + 2 − 0.5 = 2.5e9.
    # ROIC = 0.79 / 2.5 = 0.316.
    r = compute_roic(
        op_income=1e9, tax_rate=0.21, total_debt=1e9,
        total_equity=2e9, cash=0.5e9,
    )
    assert r is not None and math.isclose(r, 0.316, abs_tol=0.002)


def test_roic_none_on_negative_op_income():
    assert compute_roic(-1, 0.21, 1e9, 2e9, 0.5e9) is None


def test_roic_none_when_equity_missing():
    assert compute_roic(1e9, 0.21, 1e9, None, 0) is None


def test_roic_none_when_invested_capital_nonpositive():
    # Cash exceeds debt + equity → invested capital ≤ 0, ROIC undefined.
    assert compute_roic(1e9, 0.21, total_debt=0, total_equity=1e9, cash=2e9) is None


# ── CAPM discount rate ────────────────────────────────────────────────────────

def test_capm_discount_rate_uses_beta():
    # rf 4.3% + beta 1.0 × erp 5.0% = 9.3%
    assert math.isclose(capm_discount_rate(1.0, risk_free=0.043, erp=0.05), 0.093, abs_tol=1e-9)


def test_capm_discount_rate_rises_with_beta():
    assert capm_discount_rate(1.5) > capm_discount_rate(0.8)


def test_capm_discount_rate_defaults_to_beta_one_when_missing():
    assert capm_discount_rate(None) == capm_discount_rate(1.0)


def test_capm_discount_rate_is_clamped():
    assert capm_discount_rate(10.0) <= 0.16    # absurd high beta clamped
    assert capm_discount_rate(-5.0) >= 0.06     # negative beta floored


# ── DCF valuation range ───────────────────────────────────────────────────────

def test_dcf_range_orders_bear_below_base_below_bull():
    rng = dcf_valuation_range(fcf=10e9, shares=1e9, base_growth=0.10, base_discount=0.10)
    assert rng["bear"] < rng["base"] < rng["bull"]


def test_dcf_range_none_safe_on_missing_inputs():
    assert dcf_valuation_range(None, 1e9, 0.10, 0.10) == {"bear": None, "base": None, "bull": None}


# ── reverse_dcf_growth ────────────────────────────────────────────────────────

def test_reverse_dcf_recovers_the_growth_that_made_the_price():
    disc = 0.10
    price = dcf_intrinsic_value(10e9, 1e9, growth_rate=0.10, discount_rate=disc, terminal_growth=0.025)
    g = reverse_dcf_growth(price, 10e9, 1e9, disc, terminal_growth=0.025)
    assert g is not None and abs(g - 0.10) < 0.005


def test_reverse_dcf_higher_price_implies_higher_growth():
    disc = 0.10
    low  = reverse_dcf_growth(120.0, 10e9, 1e9, disc)
    high = reverse_dcf_growth(180.0, 10e9, 1e9, disc)
    assert low is not None and high is not None and high > low


def test_reverse_dcf_none_on_bad_inputs():
    assert reverse_dcf_growth(0, 10e9, 1e9, 0.10) is None
    assert reverse_dcf_growth(100.0, None, 1e9, 0.10) is None
    assert reverse_dcf_growth(100.0, 10e9, 0, 0.10) is None


# ── valuation_verdict ─────────────────────────────────────────────────────────

def test_verdict_undervalued_below_conservative_case():
    out = valuation_verdict(70.0, fair_low=110.0, fair_base=130.0, fair_high=160.0)
    assert out["signal"] == "Undervalued" and out["tone"] == "pass"


def test_verdict_fairly_valued_within_range_is_neutral():
    out = valuation_verdict(130.0, fair_low=110.0, fair_base=130.0, fair_high=160.0)
    assert out["signal"] == "Fairly valued" and out["tone"] == "neutral"


def test_verdict_premium_when_above_range_but_growth_plausible():
    out = valuation_verdict(200.0, fair_low=110.0, fair_base=130.0, fair_high=160.0,
                            implied_growth=0.10, reference_growth=0.08)
    assert out["tone"] == "watch"
    assert "growth" in out["signal"].lower()


def test_verdict_expensive_only_when_no_plausible_growth_justifies_price():
    out = valuation_verdict(500.0, fair_low=110.0, fair_base=130.0, fair_high=160.0,
                            implied_growth=None, reference_growth=0.08)
    assert out["signal"] == "Expensive" and out["tone"] == "fail"


def test_verdict_insufficient_without_fair_base():
    out = valuation_verdict(100.0, fair_low=None, fair_base=None, fair_high=None)
    assert out["signal"] == "INSUFFICIENT DATA"


def test_verdict_low_confidence_outside_circle_of_competence():
    out = valuation_verdict(70.0, 110.0, 130.0, 160.0, coc={"within": False, "flags": ["x"]})
    assert out["confidence"] == "Low"
    assert any("circle of competence" in c.lower() for c in out["caveats"])


def test_verdict_flags_cyclical_peak_earnings_caveat():
    out = valuation_verdict(120.0, 110.0, 130.0, 160.0, lynch={"category": "Cyclical"})
    assert any("cyclical" in c.lower() for c in out["caveats"])


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


def test_compute_valuation_exposes_capm_discount_and_dcf_range():
    out = compute_valuation(_quote(beta=1.2))
    assert out["discount_rate"] is not None and out["discount_rate"] > 0
    assert "dcf_bear" in out and "dcf_bull" in out
    assert out["dcf_bear"] is not None and out["dcf_bull"] is not None
    assert out["dcf_bear"] < out["dcf_bull"]
    assert out["inputs"]["beta"] == 1.2


def test_compute_valuation_includes_verdict():
    out = compute_valuation(_quote())
    assert "verdict" in out
    v = out["verdict"]
    assert "signal" in v and "mos" in v and "fair_base" in v


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
                "Common Stock Equity":         60e9,
                "Cash And Cash Equivalents":  30e9,
            },
        },
        "cashflow": {},
    }
    out = compute_valuation(_quote(), data)
    assert out["epv"] is not None and out["epv"] > 0
    assert out["roic"] is not None and out["roic"] > 0
