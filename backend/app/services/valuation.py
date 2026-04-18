import math
from typing import Optional


def graham_number(eps: Optional[float], bvps: Optional[float]) -> Optional[float]:
    """Graham Number = sqrt(22.5 × EPS × BVPS). Returns None if inputs are invalid."""
    if not eps or not bvps or eps <= 0 or bvps <= 0:
        return None
    return math.sqrt(22.5 * eps * bvps)


def dcf_intrinsic_value(
    fcf: float,
    shares: float,
    growth_rate: float = 0.10,
    discount_rate: float = 0.10,
    terminal_growth: float = 0.03,
    years: int = 10,
) -> Optional[float]:
    """
    10-year DCF with Gordon Growth terminal value.
    Returns intrinsic value per share, or None if inputs are invalid.
    """
    if not fcf or not shares or fcf <= 0 or shares <= 0:
        return None
    if discount_rate <= terminal_growth:
        return None

    pv = 0.0
    fcf_t = fcf
    for t in range(1, years + 1):
        fcf_t *= (1 + growth_rate)
        pv += fcf_t / (1 + discount_rate) ** t

    terminal_value = fcf_t * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv += terminal_value / (1 + discount_rate) ** years

    return round(pv / shares, 2)


def margin_of_safety(current_price: Optional[float], intrinsic_value: Optional[float]) -> Optional[float]:
    """(Intrinsic Value - Price) / Intrinsic Value × 100. Positive = undervalued."""
    if not current_price or not intrinsic_value or intrinsic_value <= 0:
        return None
    return round((intrinsic_value - current_price) / intrinsic_value * 100, 1)


def compute_valuation(quote: dict) -> dict:
    price  = quote.get("price")
    eps    = quote.get("trailingEps")
    bvps   = quote.get("bookValue")
    fcf    = quote.get("freeCashflow")
    shares = quote.get("sharesOutstanding")

    # Default growth: cap revenue growth between 3% and 25%
    raw_growth = quote.get("revenueGrowth") or 0.10
    default_growth = max(0.03, min(raw_growth, 0.25))

    graham = graham_number(eps, bvps)
    dcf_base = dcf_intrinsic_value(
        fcf, shares,
        growth_rate=default_growth,
        discount_rate=0.10,
        terminal_growth=0.03,
    )

    return {
        "graham":       round(graham, 2) if graham else None,
        "dcf_base":     dcf_base,
        "current_price": price,
        "mos_graham":   margin_of_safety(price, graham),
        "mos_dcf":      margin_of_safety(price, dcf_base),
        "inputs": {
            "eps":            eps,
            "bvps":           bvps,
            "fcf":            fcf,
            "shares":         shares,
            "default_growth": round(default_growth, 4),
        },
    }
