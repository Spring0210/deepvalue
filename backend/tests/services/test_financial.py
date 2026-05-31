"""Tests for the TTM/MRQ normalizer. Pure-function only — no network.

build_ttm_data turns annual + quarterly statements into the `data` dict the
scorecard consumes: a trailing-twelve-month income/cashflow column and a
most-recent-quarter balance (with trailing-year average invested-capital
inputs injected), with the annual columns kept behind it for trend depth."""

from __future__ import annotations

from app.services.financial import _normalize_dividend_yield, build_ttm_data


def test_dividend_yield_percent_normalized_to_fraction():
    # yfinance now returns the yield in percent (2.68 = 2.68%); the rest of the
    # app assumes a fraction, so normalize at the data layer.
    assert abs(_normalize_dividend_yield(2.68) - 0.0268) < 1e-9
    assert abs(_normalize_dividend_yield(0.35) - 0.0035) < 1e-9
    assert _normalize_dividend_yield(None) is None


def _annual():
    return {
        "financials":   {"2025-12-31": {"Total Revenue": 380.0, "Net Income": 38.0}},
        "balanceSheet": {"2025-12-31": {"Total Debt": 50.0, "Common Stock Equity": 360.0,
                                        "Cash And Cash Equivalents": 30.0}},
        "cashflow":     {"2025-12-31": {"Capital Expenditure": -18.0,
                                        "Net Income From Continuing Operations": 38.0}},
    }


def _quarterly(n=5):
    # Newest quarter first. Equity declines into the past so the trailing-year
    # average (MRQ 400 with the year-ago quarter 300) is distinct from ending.
    equities = [400.0, 390.0, 380.0, 370.0, 300.0]
    inc, bal, cf = {}, {}, {}
    for i in range(n):
        key = f"2025-q{i}"
        inc[key] = {"Total Revenue": 100.0, "Net Income": 10.0,
                    "Operating Income": 20.0, "Gross Profit": 60.0, "Basic EPS": 1.0}
        bal[key] = {"Total Debt": 50.0, "Common Stock Equity": equities[i],
                    "Cash And Cash Equivalents": 30.0}
        cf[key] = {"Capital Expenditure": -5.0, "Net Income From Continuing Operations": 10.0}
    return {"financials": inc, "balanceSheet": bal, "cashflow": cf}


def test_ttm_income_sums_last_four_quarters():
    out = build_ttm_data(_annual(), _quarterly())
    ttm = out["financials"]["TTM"]
    assert ttm["Total Revenue"] == 400.0
    assert ttm["Net Income"] == 40.0
    assert ttm["Basic EPS"] == 4.0


def test_ttm_cashflow_sums_last_four_quarters():
    out = build_ttm_data(_annual(), _quarterly())
    assert out["cashflow"]["TTM"]["Capital Expenditure"] == -20.0


def test_balance_is_mrq_with_trailing_year_average_equity():
    bal = build_ttm_data(_annual(), _quarterly())["balanceSheet"]["TTM"]
    assert bal["Common Stock Equity"] == 400.0   # MRQ point-in-time preserved
    assert bal["_TTM Avg Equity"] == 350.0        # average(MRQ 400, year-ago 300)


def test_average_falls_back_to_ending_without_year_ago_quarter():
    bal = build_ttm_data(_annual(), _quarterly(n=4))["balanceSheet"]["TTM"]
    assert bal["_TTM Avg Equity"] == 400.0        # only 4 quarters → ending only


def test_ttm_column_is_prepended_before_annual_columns():
    keys = list(build_ttm_data(_annual(), _quarterly())["financials"].keys())
    assert keys[0] == "TTM"
    assert keys[1] == "2025-12-31"   # annual retained behind TTM for trend/growth


def test_falls_back_to_annual_when_fewer_than_four_quarters():
    annual = _annual()
    out = build_ttm_data(annual, {"financials": {}, "balanceSheet": {}, "cashflow": {}})
    assert out is annual
