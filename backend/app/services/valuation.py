import math
from typing import Optional


# ── Shared helper ─────────────────────────────────────────────────────────────

def _latest(statement: dict, field: str) -> Optional[float]:
    if not statement:
        return None
    col = next(iter(statement))
    return statement[col].get(field)


# ── Valuation models ──────────────────────────────────────────────────────────

def graham_number(eps: Optional[float], bvps: Optional[float]) -> Optional[float]:
    """Graham Number = sqrt(22.5 × EPS × BVPS)."""
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
    """10-year DCF with Gordon Growth terminal value. Returns per-share intrinsic value."""
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


def fcf_yield_value(
    fcf: Optional[float],
    shares: Optional[float],
    required_yield: float = 0.07,
) -> Optional[float]:
    """
    FCF Yield Valuation: Fair Value = (FCF / shares) / required_yield.
    Required yield ≈ risk-free rate + equity risk premium (default 7%).
    """
    if not fcf or not shares or fcf <= 0 or shares <= 0 or required_yield <= 0:
        return None
    return round((fcf / shares) / required_yield, 2)


def earnings_power_value(
    nopat: Optional[float],
    shares: Optional[float],
    discount_rate: float = 0.10,
) -> Optional[float]:
    """
    Greenwald EPV: assumes zero growth, values the business as a perpetuity.
    EPV/share = NOPAT / (discount_rate × shares).
    Represents a conservative floor valuation.
    """
    if not nopat or not shares or nopat <= 0 or shares <= 0 or discount_rate <= 0:
        return None
    return round(nopat / discount_rate / shares, 2)


def margin_of_safety(current_price: Optional[float], intrinsic_value: Optional[float]) -> Optional[float]:
    """(IV − Price) / IV × 100. Positive = undervalued."""
    if not current_price or not intrinsic_value or intrinsic_value <= 0:
        return None
    return round((intrinsic_value - current_price) / intrinsic_value * 100, 1)


# ── Derived metrics ───────────────────────────────────────────────────────────

def compute_roic(
    op_income: Optional[float],
    tax_rate: Optional[float],
    total_debt: Optional[float],
    total_assets: Optional[float],
    cash: Optional[float],
) -> Optional[float]:
    """
    ROIC = NOPAT / Invested Capital.
    NOPAT = Operating Income × (1 − tax_rate).
    Invested Capital = Total Assets − Total Debt + Total Debt − Cash = Equity + Debt − Cash.
    """
    if not op_income or op_income <= 0:
        return None
    t = tax_rate if (tax_rate is not None and 0 < tax_rate < 1) else 0.21
    nopat = op_income * (1 - t)

    if total_debt is None or total_assets is None:
        return None
    equity = total_assets - total_debt
    invested_capital = equity + total_debt - (cash or 0)
    if invested_capital <= 0:
        return None
    return round(nopat / invested_capital, 4)


def circle_of_competence_check(quote: dict) -> dict:
    """
    Flags businesses outside Buffett's stated circle of competence.
    Returns {within, flags, complexity}.
    """
    flags: list[str] = []
    sector = (quote.get("sector") or "").lower()

    if "financial" in sector:
        flags.append("Financial sector: leverage and off-balance-sheet complexity make intrinsic value hard to model")

    eps = quote.get("trailingEps") or 0
    if "health" in sector and eps <= 0:
        flags.append("Unprofitable biotech/pharma: pipeline value is speculative and not modellable with DCF")

    fcf = quote.get("freeCashflow") or 0
    if fcf < 0 and eps <= 0:
        flags.append("Negative FCF and negative EPS: business is burning cash with no near-term profitability")

    peg = quote.get("pegRatio")
    if peg and peg > 3:
        flags.append(f"PEG ratio {peg:.1f}: priced for hyper-growth, not a value entry point")

    complexity = "Low" if len(flags) == 0 else "Medium" if len(flags) == 1 else "High"
    return {"within": len(flags) == 0, "flags": flags, "complexity": complexity}


# ── Top-level ─────────────────────────────────────────────────────────────────

def compute_valuation(quote: dict, data: dict | None = None) -> dict:
    price  = quote.get("price")
    eps    = quote.get("trailingEps")
    bvps   = quote.get("bookValue")
    fcf    = quote.get("freeCashflow")
    shares = quote.get("sharesOutstanding")
    mktcap = quote.get("marketCap")

    raw_growth   = quote.get("revenueGrowth") or 0.10
    default_growth = max(0.03, min(raw_growth, 0.25))

    graham   = graham_number(eps, bvps)
    dcf_base = dcf_intrinsic_value(fcf, shares, growth_rate=default_growth, discount_rate=0.10, terminal_growth=0.03)
    fcf_val  = fcf_yield_value(fcf, shares, required_yield=0.07)

    # P/FCF
    p_fcf = round(mktcap / fcf, 1) if (mktcap and fcf and fcf > 0) else None

    # EPV and ROIC — require financial statement data
    epv  = None
    roic = None
    if data:
        fin = data.get("financials", {})
        bal = data.get("balanceSheet", {})

        op_income    = _latest(fin, "Operating Income")
        tax_prov     = _latest(fin, "Tax Provision")
        pretax       = _latest(fin, "Pretax Income")
        total_debt   = _latest(bal, "Total Debt")
        total_assets = _latest(bal, "Total Assets")
        cash         = _latest(bal, "Cash And Cash Equivalents")

        tax_rate = (tax_prov / pretax) if (tax_prov and pretax and pretax > 0) else None
        nopat = (op_income * (1 - (tax_rate or 0.21))) if (op_income and op_income > 0) else None

        epv  = earnings_power_value(nopat, shares, discount_rate=0.10)
        roic = compute_roic(op_income, tax_rate, total_debt, total_assets, cash)

    coc = circle_of_competence_check(quote)

    return {
        "graham":            round(graham, 2) if graham else None,
        "dcf_base":          dcf_base,
        "fcf_yield_value":   fcf_val,
        "epv":               epv,
        "current_price":     price,
        "mos_graham":        margin_of_safety(price, graham),
        "mos_dcf":           margin_of_safety(price, dcf_base),
        "mos_fcf_yield":     margin_of_safety(price, fcf_val),
        "mos_epv":           margin_of_safety(price, epv),
        "roic":              roic,
        "price_to_fcf":      p_fcf,
        "circle_of_competence": coc,
        "inputs": {
            "eps":            eps,
            "bvps":           bvps,
            "fcf":            fcf,
            "shares":         shares,
            "default_growth": round(default_growth, 4),
        },
    }
