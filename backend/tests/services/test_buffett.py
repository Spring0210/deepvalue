"""Tests for the Buffett scorecard. Boundary cases first: sign flips, operating
losses, missing equity. The exact pass thresholds are sector-tuned elsewhere —
here we pin the bug-prone branches that silently produced wrong pass/fail."""

from __future__ import annotations

from app.services.buffett import compute_ratios


def _by_name(ratios, name):
    return next(r for r in ratios if r.name == name)


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
