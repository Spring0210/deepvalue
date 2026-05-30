import math
from typing import Optional


# ── Shared helper ─────────────────────────────────────────────────────────────

def _latest(statement: dict, field: str) -> Optional[float]:
    if not statement:
        return None
    col = next(iter(statement))
    return statement[col].get(field)


# yfinance labels equity differently across tickers; try the common fields in order.
_EQUITY_FIELDS = (
    "Stockholders Equity",
    "Common Stock Equity",
    "Total Equity Gross Minority Interest",
)


def _book_equity(bal: dict) -> Optional[float]:
    for field in _EQUITY_FIELDS:
        v = _latest(bal, field)
        if v is not None:
            return v
    return None


# ── Valuation models ──────────────────────────────────────────────────────────

def graham_number(eps: Optional[float], bvps: Optional[float]) -> Optional[float]:
    """Graham Number = sqrt(22.5 × EPS × BVPS)."""
    if not eps or not bvps or eps <= 0 or bvps <= 0:
        return None
    return math.sqrt(22.5 * eps * bvps)


# Defaults for the cost of equity. No live data feed, so these are static:
# RISK_FREE ≈ 10-yr Treasury, EQUITY_RISK_PREMIUM ≈ long-run US equity premium.
RISK_FREE = 0.043
EQUITY_RISK_PREMIUM = 0.05
_DISCOUNT_MIN = 0.06
_DISCOUNT_MAX = 0.16


def capm_discount_rate(
    beta: Optional[float],
    risk_free: float = RISK_FREE,
    erp: float = EQUITY_RISK_PREMIUM,
) -> float:
    """Cost of equity via CAPM: risk_free + beta × equity-risk-premium.

    A flat 10% for every company is the biggest DCF error — a utility and a
    biotech can't share a discount rate. Missing beta defaults to the market
    (1.0); the result is clamped to a sane band to tame yfinance outliers.
    """
    b = beta if beta is not None else 1.0
    rate = risk_free + b * erp
    return round(max(_DISCOUNT_MIN, min(_DISCOUNT_MAX, rate)), 4)


def dcf_valuation_range(
    fcf: Optional[float],
    shares: Optional[float],
    base_growth: float,
    base_discount: float,
    terminal_growth: float = 0.03,
) -> dict:
    """Bear / base / bull intrinsic values. A single-point DCF gives false
    precision; the range is why a margin of safety exists.

    Bear = lower growth + higher discount; bull = higher growth + lower discount.
    """
    bear_discount = base_discount + 0.02
    bull_discount = max(terminal_growth + 0.01, base_discount - 0.02)
    return {
        "bear": dcf_intrinsic_value(
            fcf, shares, max(0.0, base_growth - 0.04), bear_discount, terminal_growth),
        "base": dcf_intrinsic_value(
            fcf, shares, base_growth, base_discount, terminal_growth),
        "bull": dcf_intrinsic_value(
            fcf, shares, min(0.35, base_growth + 0.04), bull_discount, terminal_growth),
    }


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
    total_equity: Optional[float],
    cash: Optional[float],
) -> Optional[float]:
    """
    ROIC = NOPAT / Invested Capital (financing approach).
    NOPAT = Operating Income × (1 − tax_rate).
    Invested Capital = Total Debt + Total Equity − excess Cash.

    Uses real book equity, not an `assets − debt` proxy: that proxy folds every
    non-debt liability (payables, deferred revenue, pensions) into "capital" and
    badly understates ROIC for working-capital-heavy firms.
    """
    if not op_income or op_income <= 0:
        return None
    if total_equity is None:
        return None
    t = tax_rate if (tax_rate is not None and 0 < tax_rate < 1) else 0.21
    nopat = op_income * (1 - t)

    invested_capital = (total_debt or 0) + total_equity - (cash or 0)
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

    beta     = quote.get("beta")
    discount = capm_discount_rate(beta)

    graham   = graham_number(eps, bvps)
    dcf_range = dcf_valuation_range(fcf, shares, base_growth=default_growth, base_discount=discount)
    dcf_base  = dcf_range["base"]
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
        total_equity = _book_equity(bal)
        cash         = _latest(bal, "Cash And Cash Equivalents")

        tax_rate = (tax_prov / pretax) if (tax_prov and pretax and pretax > 0) else None
        nopat = (op_income * (1 - (tax_rate or 0.21))) if (op_income and op_income > 0) else None

        epv  = earnings_power_value(nopat, shares, discount_rate=discount)
        roic = compute_roic(op_income, tax_rate, total_debt, total_equity, cash)

    coc = circle_of_competence_check(quote)

    return {
        "graham":            round(graham, 2) if graham else None,
        "dcf_base":          dcf_base,
        "dcf_bear":          dcf_range["bear"],
        "dcf_bull":          dcf_range["bull"],
        "fcf_yield_value":   fcf_val,
        "epv":               epv,
        "current_price":     price,
        "discount_rate":     discount,
        "mos_graham":        margin_of_safety(price, graham),
        "mos_dcf":           margin_of_safety(price, dcf_base),
        "mos_dcf_bear":      margin_of_safety(price, dcf_range["bear"]),
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
            "beta":           beta,
            "discount_rate":  discount,
        },
    }
