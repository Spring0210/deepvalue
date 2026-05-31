"""Peter Lynch's six-category classifier.

Lynch's central idea: you can't judge a stock until you know *what kind* of
stock it is. A 4% grower priced like a 30% grower is a disaster; a cyclical
bought at a low P/E (peak earnings) is a trap. Each category is judged on its
own yardstick rather than a single universal rule.
"""

from typing import Optional

# yfinance sector labels whose earnings track the economic cycle.
_CYCLICAL_SECTORS = {
    "Energy", "Basic Materials", "Materials", "Industrials",
    "Consumer Cyclical", "Consumer Discretionary",
}

_FAST_GROWTH = 0.20     # ≥ 20% earnings growth = fast grower
_STALWART_GROWTH = 0.08  # 8–20% with size = stalwart
_LARGE_CAP = 10e9
_ASSET_PLAY_NET_CASH = 0.30  # net cash ≥ 30% of market cap = hidden asset value


def _latest(statement: dict, field: str) -> Optional[float]:
    if not statement:
        return None
    col = next(iter(statement))
    return statement[col].get(field)


def _net_cash_ratio(quote: dict, data: Optional[dict]) -> Optional[float]:
    """(Cash − Total Debt) / Market Cap, or None if we can't compute it."""
    mktcap = quote.get("marketCap")
    if not data or not mktcap:
        return None
    bal = data.get("balanceSheet", {})
    cash = _latest(bal, "Cash And Cash Equivalents")
    debt = _latest(bal, "Total Debt") or 0.0
    if cash is None:
        return None
    return (cash - debt) / mktcap


def _growth(quote: dict) -> float:
    g = quote.get("earningsGrowth")
    if g is None:
        g = quote.get("revenueGrowth")
    return g if g is not None else 0.0


def classify_lynch(quote: dict, data: Optional[dict] = None) -> dict:
    sector  = quote.get("sector", "") or ""
    eps     = quote.get("trailingEps")
    mktcap  = quote.get("marketCap") or 0.0
    yield_  = quote.get("dividendYield") or 0.0
    peg     = quote.get("pegRatio")
    growth  = _growth(quote)
    net_cash = _net_cash_ratio(quote, data)

    metrics: dict = {
        "growth": round(growth, 4),
        "peg": peg,
        "dividend_yield": yield_,
        "net_cash_ratio": round(net_cash, 4) if net_cash is not None else None,
    }

    # Precedence: distress and hidden-asset signals dominate the growth buckets,
    # and cyclicals are defined by sector regardless of the current growth print.
    if eps is not None and eps <= 0:
        category = "Turnaround"
        rationale = "Earnings are negative — a troubled company that must recover."
        yardstick = "Survival first: check balance-sheet strength, debt load and cash runway, not P/E."
        verdict = "Speculative until profitability and the balance sheet stabilise."

    elif net_cash is not None and net_cash >= _ASSET_PLAY_NET_CASH:
        category = "Asset Play"
        rationale = f"Net cash is {net_cash * 100:.0f}% of market cap — value not reflected in earnings."
        yardstick = "Value the hidden assets (net cash, real estate, stakes) vs market cap, not the P/E."
        verdict = "Worth a sum-of-the-parts look; the market may be ignoring the balance sheet."

    elif sector in _CYCLICAL_SECTORS:
        category = "Cyclical"
        rationale = f"{sector} earnings rise and fall with the economic cycle."
        yardstick = "Beware the P/E trap: a low P/E on peak earnings is the danger, not the bargain."
        verdict = "Time it to the cycle; judge on through-cycle earnings, not the latest quarter."

    elif growth >= _FAST_GROWTH:
        category = "Fast Grower"
        rationale = f"Earnings growing {growth * 100:.0f}% — Lynch's big winners (and biggest risks)."
        yardstick = "PEG ≤ 1: pay no more than the growth rate. Watch for growth that can't last."
        verdict = _peg_verdict(peg)

    elif growth >= _STALWART_GROWTH and mktcap >= _LARGE_CAP:
        category = "Stalwart"
        rationale = f"Large, established business growing a steady {growth * 100:.0f}%."
        yardstick = "Buy on dips at PEG ≤ 1; expect modest 30–50% gains, not multibaggers."
        verdict = _peg_verdict(peg)

    else:
        category = "Slow Grower"
        rationale = (
            f"Low growth ({growth * 100:.0f}%)"
            + (f" with a {yield_ * 100:.1f}% dividend." if yield_ else ".")
        )
        yardstick = "Own it for the dividend: check yield and payout sustainability, not capital gains."
        verdict = (
            f"Dividend yield {yield_ * 100:.1f}% is the main return driver."
            if yield_ else "Little growth and little yield — limited reason to own."
        )

    return {
        "category": category,
        "rationale": rationale,
        "yardstick": yardstick,
        "verdict": verdict,
        "metrics": metrics,
    }


def _peg_verdict(peg: Optional[float]) -> str:
    if peg is None:
        return "PEG unavailable — estimate fair value as P/E ≈ growth rate."
    if peg <= 1.0:
        return f"PEG {peg:.1f} — growth is reasonably priced (≤ 1 is Lynch's buy zone)."
    if peg <= 2.0:
        return f"PEG {peg:.1f} — fully priced; demand a margin of safety."
    return f"PEG {peg:.1f} — expensive; the price already assumes the growth continues."
