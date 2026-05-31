import math
from typing import Optional

from app.services.lynch import classify_lynch


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


def invested_capital_inputs(bal: dict) -> tuple:
    """(debt, equity, cash) for ROE/ROIC, preferring the trailing-year averages
    injected by the TTM normalizer and falling back to point-in-time book values
    (annual or MRQ). Averaging a period-average stock against a TTM flow is the
    textbook treatment; the fallback keeps annual-only data working unchanged."""
    debt   = _latest(bal, "_TTM Avg Total Debt")
    equity = _latest(bal, "_TTM Avg Equity")
    cash   = _latest(bal, "_TTM Avg Cash")
    if debt is None:
        debt = _latest(bal, "Total Debt")
    if equity is None:
        equity = _book_equity(bal)
    if cash is None:
        cash = _latest(bal, "Cash And Cash Equivalents")
    return debt, equity, cash


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


# ── Owner earnings, WACC, and the two-stage DCF (Buffett/Munger) ──────────────

def owner_earnings(
    net_income: Optional[float],
    dep_amort: Optional[float],
    capex: Optional[float],
    maintenance_capex: Optional[float] = None,
    wc_change: float = 0.0,
) -> Optional[float]:
    """Buffett owner earnings = NI + D&A − maintenance CapEx − ΔWorking capital.

    Maintenance CapEx is rarely disclosed; absent it we use total CapEx, which
    understates owner earnings for heavy growth investors — the conservative
    (safe) direction. Returns None on missing inputs. Time O(1), Space O(1).
    """
    if net_income is None or dep_amort is None or capex is None:
        return None
    maint = maintenance_capex if maintenance_capex is not None else abs(capex)
    return net_income + dep_amort - maint - (wc_change or 0.0)


def compute_wacc(
    beta: Optional[float],
    equity: Optional[float],
    debt: Optional[float],
    interest_expense: Optional[float],
    tax_rate: Optional[float],
    risk_free: float = RISK_FREE,
    erp: float = EQUITY_RISK_PREMIUM,
) -> float:
    """WACC = wE·Re + wD·Rd·(1−tax). Re via CAPM, Rd ≈ interest / debt.

    Fallbacks: no/zero debt → WACC = Re; bad Rd clamped ≤ 15%; missing tax → 21%.
    Time O(1), Space O(1).
    """
    re = capm_discount_rate(beta, risk_free, erp)
    if not debt or debt <= 0:
        return re
    rd = min(abs(interest_expense) / debt, 0.15) if interest_expense else 0.05
    t = tax_rate if (tax_rate is not None and 0 <= tax_rate < 1) else 0.21
    v = (equity or 0) + debt
    if v <= 0:
        return re
    return round((equity or 0) / v * re + debt / v * rd * (1 - t), 4)


def two_stage_dcf(
    base_cf: Optional[float],
    shares: Optional[float],
    wacc: float,
    roic: Optional[float],
    g1: float,
    n1: int = 5,
    g_terminal: float = 0.025,
    fade_years: int = 5,
) -> Optional[float]:
    """Per-share intrinsic value via a two-stage DCF on owner earnings / FCF.

    Stage 1: grow at g1 for n1 years. Stage 2: linearly fade g1 → g_terminal over
    fade_years (no flat-then-cliff artifact). Gordon terminal value.

    Munger's value-creation hurdle: growth only creates value when ROIC > WACC.
    If ROIC ≤ WACC we do NOT capitalize growth — we collapse to the no-growth
    perpetuity (growth at sub-cost-of-capital destroys value).

    Edge cases: non-positive base_cf/shares → None; wacc ≤ g_terminal → None.
    Time O(n1 + fade_years), Space O(1).
    """
    if not base_cf or base_cf <= 0 or not shares or shares <= 0:
        return None
    if wacc <= g_terminal:
        return None
    if roic is not None and roic <= wacc:
        return round((base_cf / wacc) / shares, 2)

    pv, cf = 0.0, base_cf
    for t in range(1, n1 + 1):
        cf *= (1 + g1)
        pv += cf / (1 + wacc) ** t

    g, step, yr = g1, (g1 - g_terminal) / max(fade_years, 1), n1
    for _ in range(fade_years):
        yr += 1
        g -= step
        cf *= (1 + g)
        pv += cf / (1 + wacc) ** yr

    tv = cf * (1 + g_terminal) / (wacc - g_terminal)
    pv += tv / (1 + wacc) ** yr
    return round(pv / shares, 2)


def owner_earnings_dcf_range(
    oe: Optional[float],
    shares: Optional[float],
    wacc: float,
    roic: Optional[float],
    g1: float,
    n1: int = 5,
    g_terminal: float = 0.025,
    fade_years: int = 5,
) -> dict:
    """Bear / base / bull two-stage owner-earnings DCF. Bear = lower growth +
    higher WACC; bull = higher growth + lower WACC. Time O(1), Space O(1)."""
    if not oe or oe <= 0 or not shares or shares <= 0:
        return {"bear": None, "base": None, "bull": None}
    bull_wacc = max(g_terminal + 0.01, wacc - 0.02)
    return {
        "bear": two_stage_dcf(oe, shares, wacc + 0.02, roic, max(0.0, g1 - 0.04), n1, g_terminal, fade_years),
        "base": two_stage_dcf(oe, shares, wacc, roic, g1, n1, g_terminal, fade_years),
        "bull": two_stage_dcf(oe, shares, bull_wacc, roic, min(0.30, g1 + 0.04), n1, g_terminal, fade_years),
    }


def price_decomposition(price: Optional[float], epv: Optional[float]) -> Optional[dict]:
    """Split the current price into the value of the business as-is (EPV,
    no-growth) versus the growth premium — the value↔growth bridge.

    'X% of the price is current earnings power; Y% is growth you're paying for.'
    When EPV ≥ price the stock is below its no-growth value (cheap even with zero
    growth). Returns None on bad inputs. Time O(1), Space O(1).
    """
    if not price or price <= 0 or not epv or epv <= 0:
        return None
    epv_share = min(epv / price, 1.0)
    return {
        "epv": round(epv, 2),
        "epv_share": round(epv_share, 4),
        "growth_share": round(1.0 - epv_share, 4),
        "growth_premium": round(max(price - epv, 0.0), 2),
        "below_no_growth_value": epv >= price,
    }


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


# ── Reverse DCF — what growth does the price imply? ───────────────────────────

def reverse_dcf_growth(
    price: Optional[float],
    fcf: Optional[float],
    shares: Optional[float],
    discount: float,
    years: int = 10,
    terminal_growth: float = 0.025,
) -> Optional[float]:
    """Solve for the constant FCF growth rate the current price implies.

    Inverts the single-stage DCF by bisection (it is monotonic increasing in
    growth). This answers the only honest question for a durable compounder —
    *what does the market already expect?* — which is far more robust than a
    forward point estimate that always brands quality names "overvalued".

    Returns None for invalid inputs or when the price lies outside what any
    growth in [−50%, +60%] can reproduce (i.e. priced beyond any plausible
    growth). Time O(iterations × years) = O(1) for fixed bounds, Space O(1).
    """
    if not price or price <= 0 or not fcf or fcf <= 0 or not shares or shares <= 0:
        return None
    if discount <= terminal_growth:
        return None

    def iv(g: float) -> float:
        return dcf_intrinsic_value(fcf, shares, g, discount, terminal_growth, years) or 0.0

    lo, hi = -0.50, 0.60
    if iv(lo) > price or iv(hi) < price:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if iv(mid) < price:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 4)


# ── Actionable verdict ────────────────────────────────────────────────────────

def valuation_verdict(
    price: Optional[float],
    fair_low: Optional[float],
    fair_base: Optional[float],
    fair_high: Optional[float],
    floor: Optional[float] = None,
    implied_growth: Optional[float] = None,
    reference_growth: Optional[float] = None,
    required_mos: float = 0.30,
    coc: Optional[dict] = None,
    lynch: Optional[dict] = None,
) -> dict:
    """Position price against a GROWTH-AWARE fair-value range — not a blend of
    conservative floors.

    Equal-weighting Graham/EPV (no-growth, asset-based floors) with a growth DCF
    medians a *floor* as if it were a *fair value*, which structurally labels
    durable compounders "overvalued". Here the DCF range (bear/base/bull) is the
    spine; `floor` (EPV) is reported as downside context only; and a reverse-DCF
    `implied_growth` decides whether a premium price is "priced for (plausible)
    growth" or genuinely "expensive".

    Tiers (deliberately calm — red is reserved for the rare true extreme):
      Undervalued  — price ≤ conservative case with ≥ required margin (green)
      Below fair value — price ≤ conservative case, smaller margin (green)
      Fairly valued — price within [low, high]                     (neutral)
      Premium — above the range but implied growth is plausible     (amber)
      Expensive — above the range, no plausible growth justifies it (red)

    None-safe. Time O(1), Space O(1).
    """
    if not price or price <= 0 or not fair_base or fair_base <= 0:
        return {
            "signal": "INSUFFICIENT DATA", "tone": "neutral",
            "fair_low": fair_low, "fair_base": fair_base, "fair_high": fair_high,
            "floor": floor, "price": price, "mos": None, "required_mos": required_mos,
            "implied_growth": implied_growth, "reference_growth": reference_growth,
            "confidence": "Low", "caveats": [],
            "rationale": "Not enough data to estimate a fair value.",
        }

    lo = fair_low if (fair_low and fair_low > 0) else fair_base
    hi = fair_high if (fair_high and fair_high > 0) else fair_base
    mos = (fair_base - price) / fair_base   # vs the central growth-aware estimate

    if price <= lo:
        if mos >= required_mos:
            signal, tone = "Undervalued", "pass"
            rationale = "Trades below even the conservative growth case with a margin of safety."
        else:
            signal, tone = "Below fair value", "pass"
            rationale = "Trades below the conservative growth case, but under your required margin."
    elif price <= hi:
        signal, tone = "Fairly valued", "neutral"
        rationale = "Price sits inside the growth-aware fair-value range."
    else:
        if implied_growth is None:
            signal, tone = "Expensive", "fail"
            rationale = "Price is above the optimistic case and beyond any plausible growth rate."
        elif reference_growth is not None and implied_growth > max(reference_growth, 0.0) + 0.08:
            signal, tone = "Priced for high growth", "watch"
            rationale = (
                f"Price implies ~{implied_growth * 100:.0f}%/yr growth vs ~"
                f"{reference_growth * 100:.0f}% delivered — demanding."
            )
        else:
            signal, tone = "Premium — priced for growth", "watch"
            rationale = "Above the fair-value range, but the implied growth is plausible for a quality business."

    width = (hi - lo) / fair_base if fair_base else 0.0
    confidence = "High" if width <= 0.5 else "Medium" if width <= 1.0 else "Low"
    caveats: list[str] = []
    if width > 1.0:
        caveats.append("Wide fair-value range — the inputs are uncertain; lean on the downside floor.")
    if coc and not coc.get("within", True):
        confidence = "Low"
        caveats.append("Outside a clear circle of competence — treat the estimate with extra caution.")
    if lynch and lynch.get("category") == "Cyclical":
        caveats.append("Cyclical business: judge on mid-cycle earnings, not the latest year.")
        if confidence == "High":
            confidence = "Medium"

    return {
        "signal": signal, "tone": tone,
        "fair_low": round(lo, 2), "fair_base": round(fair_base, 2), "fair_high": round(hi, 2),
        "floor": round(floor, 2) if floor else None,
        "price": round(price, 2), "mos": round(mos, 4), "required_mos": required_mos,
        "implied_growth": implied_growth, "reference_growth": reference_growth,
        "confidence": confidence, "caveats": caveats, "rationale": rationale,
    }


# ── Archetype routing — match the lens to the business ────────────────────────

_METHOD_LABELS = {
    "owner_dcf":   "Owner-earnings DCF",
    "reverse_dcf": "Reverse DCF",
    "graham":      "Graham number",
    "epv":         "Earnings power value",
    "fcf_yield":   "FCF yield value",
    "dcf_fcf":     "FCF DCF",
}

# Per archetype: method → (tier, reason). No serious investor values a
# wide-moat compounder, a peak-earnings cyclical, and a turnaround the same way.
_LENS_TABLE: dict = {
    "compounder": {
        "owner_dcf":   ("primary",        "Durable compounder — value its owner earnings and growth."),
        "reverse_dcf": ("primary",        "Test the growth the price implies against the moat."),
        "epv":         ("secondary",      "No-growth floor — the downside if growth stalls."),
        "fcf_yield":   ("secondary",      "Cross-check on cash generation."),
        "dcf_fcf":     ("secondary",      "Interactive sandbox; the owner-earnings DCF is the spine."),
        "graham":      ("not_applicable", "Asset-light; buybacks distort book value — the Graham number misleads here."),
    },
    "cyclical": {
        "epv":         ("primary",        "Value mid-cycle earnings power, not the peak."),
        "graham":      ("secondary",      "Asset value is a cycle-resistant anchor."),
        "owner_dcf":   ("secondary",      "Use normalized mid-cycle earnings, not the latest year."),
        "reverse_dcf": ("secondary",      "Implied growth off peak earnings can mislead."),
        "fcf_yield":   ("not_applicable", "Peak-cycle cash flow overstates a sustainable yield."),
        "dcf_fcf":     ("not_applicable", "Single-year cash flow misleads across the cycle."),
    },
    "slow_grower": {
        "graham":      ("primary",        "Asset/earnings value suits a mature, low-growth business."),
        "epv":         ("primary",        "Earnings power, with little growth to add."),
        "fcf_yield":   ("secondary",      "Dividend / cash yield is the core return."),
        "owner_dcf":   ("secondary",      "Limited growth to capitalize."),
        "reverse_dcf": ("secondary",      "Modest growth expectations to sanity-check."),
        "dcf_fcf":     ("secondary",      "Interactive cash-flow sandbox."),
    },
    "asset_play": {
        "graham":      ("primary",        "Value is in the assets — book/asset value is the anchor."),
        "epv":         ("secondary",      "Earnings power as a secondary check."),
        "owner_dcf":   ("not_applicable", "Value is in the assets, not the earnings stream."),
        "reverse_dcf": ("not_applicable", "Earnings growth is not the thesis."),
        "fcf_yield":   ("not_applicable", "Cash flow isn't where the value sits."),
        "dcf_fcf":     ("not_applicable", "Cash flow isn't where the value sits."),
    },
    "turnaround": {
        "graham":      ("secondary",      "Asset value — the downside if it survives."),
        "epv":         ("secondary",      "Only meaningful once earnings normalize."),
        "owner_dcf":   ("not_applicable", "Earnings aren't normalized — a DCF is speculative."),
        "reverse_dcf": ("not_applicable", "No stable earnings base to imply growth from."),
        "fcf_yield":   ("not_applicable", "Cash flow is depressed or negative."),
        "dcf_fcf":     ("not_applicable", "Cash flow is depressed or negative."),
    },
    "general": {
        "owner_dcf":   ("primary",        "Value the business on its owner earnings and growth."),
        "epv":         ("secondary",      "No-growth floor."),
        "fcf_yield":   ("secondary",      "Cross-check on cash generation."),
        "graham":      ("secondary",      "Conservative asset/earnings anchor."),
        "reverse_dcf": ("secondary",      "Growth the price implies."),
        "dcf_fcf":     ("secondary",      "Interactive cash-flow sandbox."),
    },
}


def _archetype(lynch_category: Optional[str], moat_strength: Optional[str]) -> str:
    if lynch_category == "Turnaround":
        return "turnaround"
    if lynch_category == "Asset Play":
        return "asset_play"
    if lynch_category == "Cyclical":
        return "cyclical"
    if lynch_category in ("Fast Grower", "Stalwart") or moat_strength == "Wide":
        return "compounder"
    if lynch_category == "Slow Grower":
        return "slow_grower"
    return "general"


def valuation_lenses(lynch_category: Optional[str], moat_strength: Optional[str] = None) -> dict:
    """Which valuation methods are primary / contextual / not-suited for this
    business archetype (from the Lynch category, optionally refined by moat).

    Drives the UI to emphasize the right lenses and suppress the wrong ones —
    e.g. it hides the Graham number for an asset-light compounder (the original
    Apple bug) and makes asset value primary for an asset play. Time O(1).
    """
    table = _LENS_TABLE[_archetype(lynch_category, moat_strength)]
    return {
        key: {"label": _METHOD_LABELS[key], "tier": tier, "reason": reason}
        for key, (tier, reason) in table.items()
    }


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

    # EPV, ROIC, WACC and the two-stage owner-earnings DCF — need statement data
    epv  = None
    roic = None
    wacc = None
    oe   = None
    owner_range = {"bear": None, "base": None, "bull": None}
    if data:
        fin = data.get("financials", {})
        bal = data.get("balanceSheet", {})
        cf  = data.get("cashflow", {})

        op_income    = _latest(fin, "Operating Income")
        tax_prov     = _latest(fin, "Tax Provision")
        pretax       = _latest(fin, "Pretax Income")
        interest     = _latest(fin, "Interest Expense")
        net_income   = _latest(fin, "Net Income")
        dep_amort    = _latest(cf, "Depreciation And Amortization") or _latest(fin, "Reconciled Depreciation")
        capex        = _latest(cf, "Capital Expenditure")
        total_debt, total_equity, cash = invested_capital_inputs(bal)

        tax_rate = (tax_prov / pretax) if (tax_prov and pretax and pretax > 0) else None
        nopat = (op_income * (1 - (tax_rate or 0.21))) if (op_income and op_income > 0) else None

        epv  = earnings_power_value(nopat, shares, discount_rate=discount)
        roic = compute_roic(op_income, tax_rate, total_debt, total_equity, cash)
        wacc = compute_wacc(beta, total_equity, total_debt, interest, tax_rate)
        oe   = owner_earnings(net_income, dep_amort, capex)
        owner_range = owner_earnings_dcf_range(oe, shares, wacc, roic, default_growth)

    coc = circle_of_competence_check(quote)
    lynch = classify_lynch(quote, data)
    lenses = valuation_lenses(lynch.get("category"))
    implied_growth = reverse_dcf_growth(price, fcf, shares, discount)
    decomposition = price_decomposition(price, epv)

    # The two-stage owner-earnings DCF is the credible fair-value spine; fall
    # back to the single-stage FCF range when statement data is unavailable.
    spine = owner_range if owner_range["base"] else dcf_range
    verdict = valuation_verdict(
        price,
        fair_low=spine["bear"], fair_base=spine["base"], fair_high=spine["bull"],
        floor=epv,
        implied_growth=implied_growth, reference_growth=default_growth,
        coc=coc, lynch=lynch,
    )

    return {
        "verdict":           verdict,
        "graham":            round(graham, 2) if graham else None,
        "dcf_base":          dcf_base,
        "dcf_bear":          dcf_range["bear"],
        "dcf_bull":          dcf_range["bull"],
        "fcf_yield_value":   fcf_val,
        "epv":               epv,
        "owner_earnings_dcf": owner_range,
        "wacc":              wacc,
        "price_decomposition": decomposition,
        "lenses":            lenses,
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
        "lynch":             lynch,
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
