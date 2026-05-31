"""Tests for the Buffett scorecard. Boundary cases first: sign flips, operating
losses, missing equity. The exact pass thresholds are sector-tuned elsewhere —
here we pin the bug-prone branches that silently produced wrong pass/fail."""

from __future__ import annotations

from app.services.buffett import (
    BuffettRatio,
    _ramp_high,
    _ramp_low,
    compute_ratios,
    compute_weighted_score,
)


def _by_name(ratios, name):
    return next(r for r in ratios if r.name == name)


def _stub(score, weight):
    return BuffettRatio(
        name="x", value=None, threshold="", passes=None, description="",
        buffett_logic="", category="", equation="", weight=weight, score=score,
    )


def _data(fin=None, bal=None, cf=None):
    return {"financials": fin or {}, "balanceSheet": bal or {}, "cashflow": cf or {}}


def _one_year(fields):
    return {"2024-12-31": fields}


# ── A2: Adjusted Debt-to-Equity uses real book equity ─────────────────────────

def test_debt_to_equity_uses_real_book_equity_not_assets_proxy():
    # Real equity 100, debt 200 → D/E = 2.0 (fails). The old `assets − debt`
    # proxy (1000 − 200 = 800) would have yielded 0.25 and wrongly passed.
    bal = _one_year({
        "Total Debt":           200.0,
        "Total Assets":        1000.0,
        "Common Stock Equity":  100.0,
    })
    r = _by_name(compute_ratios(_data(bal=bal)), "Adj. Debt-to-Equity")
    assert r.value is not None and abs(r.value - 2.0) < 1e-6
    assert r.passes is False


def test_debt_to_equity_fails_on_negative_equity():
    bal = _one_year({
        "Total Debt":           100.0,
        "Total Assets":          80.0,
        "Common Stock Equity":  -50.0,
    })
    r = _by_name(compute_ratios(_data(bal=bal)), "Adj. Debt-to-Equity")
    assert r.passes is False


def test_debt_to_equity_na_when_equity_missing():
    bal = _one_year({"Total Debt": 100.0, "Total Assets": 80.0})
    r = _by_name(compute_ratios(_data(bal=bal)), "Adj. Debt-to-Equity")
    assert r.passes is None


# ── A3: growth ratios are sign-aware ──────────────────────────────────────────

def test_eps_growth_fails_when_loss_deepens():
    # EPS −1 → −2 (more negative). Old ratio 2.0 wrongly passed (> 1.0).
    fin = {"2024": {"Basic EPS": -2.0}, "2023": {"Basic EPS": -1.0}}
    r = _by_name(compute_ratios(_data(fin=fin)), "EPS Growth (YoY)")
    assert r.passes is False


def test_eps_growth_fails_when_current_negative_even_if_improving():
    # −2 → −1 improves but EPS is still negative → not "positive & growing".
    fin = {"2024": {"Basic EPS": -1.0}, "2023": {"Basic EPS": -2.0}}
    r = _by_name(compute_ratios(_data(fin=fin)), "EPS Growth (YoY)")
    assert r.passes is False


def test_eps_growth_passes_when_positive_and_growing():
    fin = {"2024": {"Basic EPS": 3.0}, "2023": {"Basic EPS": 2.0}}
    r = _by_name(compute_ratios(_data(fin=fin)), "EPS Growth (YoY)")
    assert r.passes is True


def test_retained_earnings_credits_recovery_from_deficit():
    # Deficit shrinking (−2 → −1) is an improvement and should pass.
    bal = {"2024": {"Retained Earnings": -1.0}, "2023": {"Retained Earnings": -2.0}}
    r = _by_name(compute_ratios(_data(bal=bal)), "Retained Earnings Growth")
    assert r.passes is True


def test_retained_earnings_fails_when_deficit_deepens():
    bal = {"2024": {"Retained Earnings": -2.0}, "2023": {"Retained Earnings": -1.0}}
    r = _by_name(compute_ratios(_data(bal=bal)), "Retained Earnings Growth")
    assert r.passes is False


# ── A4: interest burden must not pass during an operating loss ─────────────────

def test_interest_margin_fails_on_operating_loss():
    # Operating loss can't cover interest; abs() previously hid this as a pass.
    fin = _one_year({"Operating Income": -100.0, "Interest Expense": -10.0})
    r = _by_name(compute_ratios(_data(fin=fin)), "Interest Expense Margin")
    assert r.passes is False


def test_interest_margin_passes_with_low_interest_burden():
    fin = _one_year({"Operating Income": 1000.0, "Interest Expense": -50.0})
    r = _by_name(compute_ratios(_data(fin=fin)), "Interest Expense Margin")
    assert r.value is not None and abs(r.value - 0.05) < 1e-6
    assert r.passes is True


# ── B1: continuous (graded) scoring ───────────────────────────────────────────

def test_ramp_high_partial_credit():
    assert _ramp_high(0.40, 0.40, 0.20) == 1.0   # at/above knee → full
    assert _ramp_high(0.50, 0.40, 0.20) == 1.0   # above knee → capped
    assert _ramp_high(0.30, 0.40, 0.20) == 0.5   # midpoint
    assert _ramp_high(0.20, 0.40, 0.20) == 0.0   # at edge
    assert _ramp_high(0.10, 0.40, 0.20) == 0.0   # below edge
    assert _ramp_high(None, 0.40, 0.20) is None


def test_ramp_low_partial_credit():
    assert _ramp_low(0.30, 0.30, 0.60) == 1.0    # at/below knee → full
    assert _ramp_low(0.45, 0.30, 0.60) == 0.5    # midpoint
    assert _ramp_low(0.60, 0.30, 0.60) == 0.0    # at edge
    assert _ramp_low(0.90, 0.30, 0.60) == 0.0    # above edge
    assert _ramp_low(None, 0.30, 0.60) is None


def test_gross_margin_gets_partial_score_below_threshold():
    # 30% gross margin vs 40% threshold (floor 20%) → graded score 0.5, but the
    # strict pass badge still fails (it is below the stated 40% threshold).
    fin = _one_year({"Gross Profit": 30.0, "Total Revenue": 100.0})
    r = _by_name(compute_ratios(_data(fin=fin)), "Gross Margin")
    assert r.passes is False
    assert r.score is not None and abs(r.score - 0.5) < 1e-6


def test_binary_metric_score_mirrors_pass():
    # EPS growth is a hard gate, not a ramp → score is 1.0 / 0.0 / None.
    fin = {"2024": {"Basic EPS": 3.0}, "2023": {"Basic EPS": 2.0}}
    r = _by_name(compute_ratios(_data(fin=fin)), "EPS Growth (YoY)")
    assert r.passes is True and r.score == 1.0


def test_weighted_score_uses_continuous_score():
    assert compute_weighted_score([_stub(0.5, 0.5), _stub(1.0, 0.5)]) == 75.0


def test_weighted_score_ignores_na_metrics():
    assert compute_weighted_score([_stub(None, 0.5), _stub(1.0, 0.5)]) == 100.0


# ── B2: ROIC and ROE on the scorecard ─────────────────────────────────────────

def test_roic_metric_present_and_graded():
    # NOPAT = 100 × (1 − 0.21) = 79; IC = debt 100 + equity 400 − cash 0 = 500.
    # ROIC = 79 / 500 = 0.158 → above the 12% knee → full credit, passes.
    data = _data(
        fin=_one_year({
            "Operating Income": 100.0, "Tax Provision": 21.0,
            "Pretax Income": 100.0, "Net Income": 79.0,
        }),
        bal=_one_year({
            "Total Debt": 100.0, "Common Stock Equity": 400.0,
            "Cash And Cash Equivalents": 0.0,
        }),
    )
    r = _by_name(compute_ratios(data), "ROIC")
    assert r.value is not None and abs(r.value - 0.158) < 0.002
    assert r.passes is True and r.score == 1.0


def test_roe_metric_present():
    data = _data(
        fin=_one_year({"Net Income": 80.0}),
        bal=_one_year({"Common Stock Equity": 400.0}),
    )
    r = _by_name(compute_ratios(data), "ROE (TTM)")
    assert r.value is not None and abs(r.value - 0.20) < 1e-6
    assert r.passes is True


def test_roe_fails_on_negative_equity():
    data = _data(
        fin=_one_year({"Net Income": 80.0}),
        bal=_one_year({"Common Stock Equity": -50.0}),
    )
    r = _by_name(compute_ratios(data), "ROE (TTM)")
    assert r.passes is False


def test_roe_na_when_equity_missing():
    data = _data(fin=_one_year({"Net Income": 80.0}))
    r = _by_name(compute_ratios(data), "ROE (TTM)")
    assert r.value is None and r.passes is None and r.score is None


def test_roe_and_roic_use_trailing_average_equity_when_injected():
    # The TTM normalizer injects "_TTM Avg Equity"; ROE/ROIC must prefer it over
    # the point-in-time book equity.
    data = _data(
        fin=_one_year({"Net Income": 40.0, "Operating Income": 50.0,
                       "Tax Provision": 10.0, "Pretax Income": 50.0}),
        bal=_one_year({
            "Common Stock Equity": 400.0,   # point-in-time
            "_TTM Avg Equity": 200.0,        # trailing-year average (preferred)
            "_TTM Avg Total Debt": 0.0,
            "_TTM Avg Cash": 0.0,
        }),
    )
    roe = _by_name(compute_ratios(data), "ROE (TTM)")
    assert abs(roe.value - 0.20) < 1e-6   # 40 / 200 (avg), not 40 / 400

    # NOPAT = 50 × (1 − 0.20 tax) = 40; IC = avg equity 200 → ROIC 0.20 (not 0.10).
    roic = _by_name(compute_ratios(data), "ROIC")
    assert abs(roic.value - 0.20) < 1e-6


def test_scorecard_has_sixteen_metrics_and_weights_sum_to_one():
    ratios = compute_ratios(_data())
    assert len(ratios) == 16
    assert abs(sum(r.weight for r in ratios) - 1.0) < 0.001
