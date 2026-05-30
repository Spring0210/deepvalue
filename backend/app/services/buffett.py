from dataclasses import dataclass
from typing import Optional

from app.services.valuation import compute_roic


@dataclass
class BuffettRatio:
    name: str
    value: Optional[float]
    threshold: str
    passes: Optional[bool]
    description: str
    buffett_logic: str
    category: str
    equation: str
    weight: float   # contribution to weighted score (all weights sum to 1.0)
    score: Optional[float] = None   # graded 0..1 credit (None = N/A); feeds the gauge


def _div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _latest(statement: dict, field: str) -> Optional[float]:
    if not statement:
        return None
    col = next(iter(statement))
    return statement[col].get(field)


def _nth(statement: dict, field: str, n: int) -> Optional[float]:
    cols = list(statement.keys())
    if n >= len(cols):
        return None
    return statement[cols[n]].get(field)


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


# ── Graded scoring ────────────────────────────────────────────────────────────
# Binary pass/fail throws away the distance from the threshold: a 39% and a 12%
# gross margin both "fail" a 40% gate and contribute nothing. These ramps give
# linear partial credit between a full-credit knee and a zero-credit edge.

def _ramp_high(value: Optional[float], knee: float, edge: float) -> Optional[float]:
    """Higher-is-better: 1.0 at/above `knee`, 0.0 at/below `edge`, linear between."""
    if value is None:
        return None
    if value >= knee:
        return 1.0
    if value <= edge:
        return 0.0
    return round((value - edge) / (knee - edge), 3)


def _ramp_low(value: Optional[float], knee: float, edge: float) -> Optional[float]:
    """Lower-is-better: 1.0 at/below `knee`, 0.0 at/above `edge`, linear between."""
    if value is None:
        return None
    if value <= knee:
        return 1.0
    if value >= edge:
        return 0.0
    return round((edge - value) / (edge - knee), 3)


def _binary_score(passes: Optional[bool]) -> Optional[float]:
    if passes is None:
        return None
    return 1.0 if passes else 0.0


def _graded(
    value: Optional[float], kind: str, knee: float, edge: float, passes: Optional[bool],
) -> Optional[float]:
    """Continuous score for ramp metrics; falls back to the binary pass flag when
    the value is missing but the metric was still judged (e.g. an operating loss
    forced to fail)."""
    s = _ramp_high(value, knee, edge) if kind == "high" else _ramp_low(value, knee, edge)
    return s if s is not None else _binary_score(passes)


# Ramp metrics get graded credit at construction; everything else mirrors `passes`.
_RAMP_METRICS = {
    "Gross Margin", "SG&A Margin", "R&D Margin", "Depreciation Margin",
    "Interest Expense Margin", "Net Profit Margin", "Adj. Debt-to-Equity",
    "CapEx Margin", "ROIC", "ROE",
}


def _sector_threshold(sector: str, metric: str) -> tuple[str, float]:
    """Return (threshold_label, numeric_limit) adjusted for sector norms."""
    s = sector.lower()
    is_tech      = "technology" in s or "software" in s
    is_fin       = "financial" in s
    is_health    = "health" in s or "biotech" in s or "pharma" in s
    is_util      = "utilit" in s
    is_energy    = "energy" in s
    is_mats      = "materials" in s
    is_realestate = "real estate" in s
    is_staples   = "consumer defensive" in s or "consumer staple" in s

    if metric == "Gross Margin":
        if is_fin:                          return "≥ 15%", 0.15
        if is_util or is_staples:           return "≥ 25%", 0.25
        if is_energy or is_mats:            return "≥ 20%", 0.20
        return "≥ 40%", 0.40

    if metric == "R&D Margin":
        if is_tech:                         return "≤ 60%", 0.60
        if is_health:                       return "≤ 80%", 0.80
        return "≤ 30%", 0.30

    if metric == "SG&A Margin":
        if is_tech or is_health:            return "≤ 50%", 0.50
        return "≤ 30%", 0.30

    if metric == "Net Profit Margin":
        if is_fin or is_util or is_energy or is_mats or is_staples:
            return "≥ 10%", 0.10
        return "≥ 20%", 0.20

    if metric == "Interest Expense Margin":
        if is_fin:                          return "≤ 80%", 0.80
        if is_util:                         return "≤ 40%", 0.40
        return "≤ 15%", 0.15

    if metric == "Adj. Debt-to-Equity":
        if is_fin:                          return "< 5.0",  5.0
        if is_util:                         return "< 2.0",  2.0
        if is_realestate:                   return "< 2.5",  2.5
        return "< 0.80", 0.80

    if metric == "CapEx Margin":
        if is_util:                         return "< 75%", 0.75
        if is_energy:                       return "< 60%", 0.60
        if is_realestate:                   return "< 80%", 0.80
        return "< 25%", 0.25

    return "", 0.0  # unreachable


def compute_weighted_score(ratios: list[BuffettRatio]) -> float:
    """
    Weighted score 0-100, normalized to exclude N/A metrics. Uses graded `score`
    (0..1) so metrics near their threshold earn partial credit:
    Score = sum(weight × score) / sum(weight for non-NA) × 100.
    """
    scored_weight = sum(r.weight for r in ratios if r.score is not None)
    if scored_weight == 0:
        return 0.0
    earned = sum(r.weight * r.score for r in ratios if r.score is not None)
    return round(earned / scored_weight * 100, 1)


def compute_trend_adjustment(data: dict) -> float:
    """
    Score adjustment based on multi-year metric trends. Range: −10 to +5.

    Bonus:   EPS grew 3 consecutive years (+3), Revenue grew 3 years (+2).
    Penalty: EPS fell 2+ consecutive years (−5), Revenue fell 2+ years (−3),
             Net Income fell 2+ consecutive years (−2).
    """
    fin = data.get("financials", {})

    eps = [_nth(fin, "Basic EPS", i) for i in range(4)]
    rev = [_nth(fin, "Total Revenue", i) for i in range(4)]
    net = [_nth(fin, "Net Income", i) for i in range(3)]

    adj = 0.0

    # EPS trend (index 0 = most recent year)
    if all(e is not None for e in eps):
        if eps[0] > eps[1] > eps[2] > eps[3]:  # type: ignore[operator]
            adj += 3.0
        elif eps[0] < eps[1] and eps[1] < eps[2]:  # type: ignore[operator]
            adj -= 5.0
        elif eps[0] < eps[1]:  # type: ignore[operator]
            adj -= 2.0

    # Revenue trend
    if all(r is not None for r in rev):
        if rev[0] > rev[1] > rev[2] > rev[3]:  # type: ignore[operator]
            adj += 2.0
        elif rev[0] < rev[1] and rev[1] < rev[2]:  # type: ignore[operator]
            adj -= 3.0

    # Net Income freefall
    if all(n is not None for n in net):
        if net[0] < net[1] and net[1] < net[2]:  # type: ignore[operator]
            adj -= 2.0

    return round(max(-10.0, min(5.0, adj)), 1)


def compute_ratios(data: dict, sector: str = "") -> list[BuffettRatio]:
    fin = data.get("financials", {})
    bal = data.get("balanceSheet", {})
    cf  = data.get("cashflow", {})

    ratios: list[BuffettRatio] = []

    # ── Income Statement ──────────────────────────────────────────────────────

    gross_profit = _latest(fin, "Gross Profit")
    revenue      = _latest(fin, "Total Revenue")
    op_income    = _latest(fin, "Operating Income")

    # 1. Gross Margin
    gm = _div(gross_profit, revenue)
    gm_thresh, gm_limit = _sector_threshold(sector, "Gross Margin")
    ratios.append(BuffettRatio(
        name="Gross Margin", value=gm, threshold=gm_thresh,
        passes=(gm >= gm_limit) if gm is not None else None,
        score=_ramp_high(gm, gm_limit, gm_limit * 0.5),
        equation="Gross Profit / Total Revenue",
        description="Measures how much revenue remains after direct production costs.",
        buffett_logic="Signals a durable competitive advantage — the company isn't competing on price.",
        category="Income Statement", weight=0.10,
    ))

    # 2. SG&A Margin
    sga  = _latest(fin, "Selling General And Administration")
    sgam = _div(sga, gross_profit)
    sga_thresh, sga_limit = _sector_threshold(sector, "SG&A Margin")
    ratios.append(BuffettRatio(
        name="SG&A Margin", value=sgam, threshold=sga_thresh,
        passes=(sgam <= sga_limit) if sgam is not None else None,
        score=_ramp_low(sgam, sga_limit, sga_limit * 2),
        equation="SG&A Expense / Gross Profit",
        description="Selling, General & Administrative expenses as a share of gross profit.",
        buffett_logic="Wide-moat companies don't need heavy overhead spending to operate.",
        category="Income Statement", weight=0.05,
    ))

    # 3. R&D Margin
    rnd  = _latest(fin, "Research And Development")
    rndm = _div(rnd, gross_profit)
    rnd_thresh, rnd_limit = _sector_threshold(sector, "R&D Margin")
    ratios.append(BuffettRatio(
        name="R&D Margin", value=rndm, threshold=rnd_thresh,
        passes=(rndm <= rnd_limit) if rndm is not None else None,
        score=_ramp_low(rndm, rnd_limit, rnd_limit * 2),
        equation="R&D Expense / Gross Profit",
        description="Research & Development spending as a share of gross profit.",
        buffett_logic="Heavy R&D dependence means the competitive advantage isn't guaranteed to last.",
        category="Income Statement", weight=0.04,
    ))

    # 4. Depreciation Margin (no sector adjustment — asset-lightness is universal)
    dep  = _latest(fin, "Reconciled Depreciation")
    depm = _div(dep, gross_profit)
    ratios.append(BuffettRatio(
        name="Depreciation Margin", value=depm, threshold="≤ 10%",
        passes=(depm <= 0.10) if depm is not None else None,
        score=_ramp_low(depm, 0.10, 0.20),
        equation="Reconciled Depreciation / Gross Profit",
        description="Depreciation & amortization as a share of gross profit.",
        buffett_logic="Great businesses don't need heavy depreciating assets to maintain their competitive edge.",
        category="Income Statement", weight=0.04,
    ))

    # 5. Interest Expense Margin
    interest = _latest(fin, "Interest Expense")
    int_thresh, int_limit = _sector_threshold(sector, "Interest Expense Margin")
    # An operating loss can't cover any interest. abs() used to mask this: a
    # negative/negative ratio looked like a small "passing" burden.
    intm: Optional[float] = None
    intm_pass: Optional[bool] = None
    if interest is not None and op_income is not None:
        if op_income > 0:
            intm = abs(interest) / op_income
            intm_pass = intm <= int_limit
        else:
            intm_pass = False
    ratios.append(BuffettRatio(
        name="Interest Expense Margin", value=intm, threshold=int_thresh,
        passes=intm_pass,
        score=_graded(intm, "low", int_limit, int_limit * 2, intm_pass),
        equation="Interest Expense / Operating Income",
        description="How much of operating income is consumed by interest payments.",
        buffett_logic="Great businesses self-finance with earnings — they don't need much debt.",
        category="Income Statement", weight=0.06,
    ))

    # 6. Effective Tax Rate (no sector adjustment)
    tax    = _latest(fin, "Tax Provision")
    pretax = _latest(fin, "Pretax Income")
    taxr   = _div(tax, pretax)
    ratios.append(BuffettRatio(
        name="Effective Tax Rate", value=taxr, threshold="15% – 30%",
        passes=(0.15 <= taxr <= 0.30) if taxr is not None else None,
        equation="Tax Provision / Pre-Tax Income",
        description="The actual tax rate paid on pre-tax income.",
        buffett_logic="Highly profitable companies pay full taxes — they can't shelter extraordinary income.",
        category="Income Statement", weight=0.02,
    ))

    # 7. Net Profit Margin
    net_income = _latest(fin, "Net Income")
    nm = _div(net_income, revenue)
    nm_thresh, nm_limit = _sector_threshold(sector, "Net Profit Margin")
    ratios.append(BuffettRatio(
        name="Net Profit Margin", value=nm, threshold=nm_thresh,
        passes=(nm >= nm_limit) if nm is not None else None,
        score=_ramp_high(nm, nm_limit, nm_limit * 0.5),
        equation="Net Income / Total Revenue",
        description="Percentage of revenue that becomes net profit.",
        buffett_logic="Great companies consistently convert a high percentage of revenue into net profit.",
        category="Income Statement", weight=0.09,
    ))

    # 8. EPS Growth (YoY) — no sector adjustment
    eps_0      = _nth(fin, "Basic EPS", 0)
    eps_1      = _nth(fin, "Basic EPS", 1)
    eps_growth = _div(eps_0, eps_1)
    # Judge on the signed values, not the raw ratio: two negative years give a
    # ratio > 1.0 when the loss *deepens*, which used to read as a false pass.
    eps_pass = (eps_0 > eps_1 and eps_0 > 0) if (eps_0 is not None and eps_1 is not None) else None
    ratios.append(BuffettRatio(
        name="EPS Growth (YoY)", value=eps_growth, threshold="> 1.0 (positive & growing)",
        passes=eps_pass,
        equation="EPS (Year N) / EPS (Year N−1)",
        description="Year-over-year growth ratio of basic earnings per share.",
        buffett_logic="Great companies grow earnings per share every year without fail.",
        category="Income Statement", weight=0.08,
    ))

    # ── Returns on Capital ────────────────────────────────────────────────────
    # Munger: ROIC is the single most important metric; Buffett leans on ROE.
    # Both are computed from the statements so compute_ratios stays (data, sector).

    bs_equity = _book_equity(bal)

    # 9. ROIC (return on invested capital)
    tax_prov = _latest(fin, "Tax Provision")
    pretax   = _latest(fin, "Pretax Income")
    tax_rate = (tax_prov / pretax) if (tax_prov and pretax and pretax > 0) else None
    roic = compute_roic(
        op_income, tax_rate, _latest(bal, "Total Debt"), bs_equity,
        _latest(bal, "Cash And Cash Equivalents"),
    )
    ratios.append(BuffettRatio(
        name="ROIC", value=roic, threshold="≥ 12%",
        passes=(roic >= 0.12) if roic is not None else None,
        score=_ramp_high(roic, 0.12, 0.06),
        equation="NOPAT / (Total Debt + Equity − Cash)",
        description="After-tax operating return on the capital the business employs.",
        buffett_logic="Munger's key test: durable businesses compound capital at high ROIC.",
        category="Returns on Capital", weight=0.12,
    ))

    # 10. ROE (return on equity)
    net_income_re = _latest(fin, "Net Income")
    roe: Optional[float] = None
    roe_pass: Optional[bool] = None
    if net_income_re is not None and bs_equity is not None:
        if bs_equity > 0:
            roe = net_income_re / bs_equity
            roe_pass = roe >= 0.15
        else:
            roe_pass = False   # negative book equity is a red flag, not a high ROE
    ratios.append(BuffettRatio(
        name="ROE", value=roe, threshold="≥ 15%",
        passes=roe_pass,
        score=_graded(roe, "high", 0.15, 0.075, roe_pass),
        equation="Net Income / Total Equity",
        description="Net profit generated on shareholders' equity.",
        buffett_logic="Buffett favours businesses that earn consistently high returns on equity.",
        category="Returns on Capital", weight=0.10,
    ))

    # ── Balance Sheet ─────────────────────────────────────────────────────────

    # 11. Cash vs Current Debt (no sector adjustment)
    cash         = _latest(bal, "Cash And Cash Equivalents")
    current_debt = _latest(bal, "Current Debt")
    cvd = _div(cash, current_debt)
    ratios.append(BuffettRatio(
        name="Cash vs Current Debt", value=cvd, threshold="> 1.0 (cash exceeds debt)",
        passes=(cvd > 1.0) if cvd is not None else None,
        equation="Cash & Equivalents / Current Debt",
        description="Whether the company holds more cash than its near-term debt obligations.",
        buffett_logic="Great companies generate so much cash they hold more than their near-term debt.",
        category="Balance Sheet", weight=0.06,
    ))

    # 12. Adjusted Debt-to-Equity
    total_debt = _latest(bal, "Total Debt")
    equity     = _book_equity(bal)
    dte_thresh, dte_limit = _sector_threshold(sector, "Adj. Debt-to-Equity")
    # Use real book equity, not `assets − debt`: that proxy folds payables,
    # deferred revenue and pensions into "equity" and understates leverage.
    # Negative equity is itself a failure, not a pass via a negative ratio.
    dte: Optional[float] = None
    dte_pass: Optional[bool] = None
    if total_debt is not None and equity is not None:
        if equity > 0:
            dte = total_debt / equity
            dte_pass = dte < dte_limit
        else:
            dte_pass = False
    ratios.append(BuffettRatio(
        name="Adj. Debt-to-Equity", value=dte, threshold=dte_thresh,
        passes=dte_pass,
        score=_graded(dte, "low", dte_limit, dte_limit * 2, dte_pass),
        equation="Total Debt / Total Equity",
        description="Debt relative to shareholders' equity.",
        buffett_logic="Great companies fund growth through equity and retained earnings, not debt.",
        category="Balance Sheet", weight=0.09,
    ))

    # 13. Preferred Stock (no sector adjustment)
    preferred = _latest(bal, "Preferred Stock")
    ratios.append(BuffettRatio(
        name="Preferred Stock", value=preferred, threshold="None (= $0)",
        passes=(preferred is None or preferred == 0),
        equation="Preferred Stock balance on Balance Sheet",
        description="Whether the company has issued preferred stock.",
        buffett_logic="Great companies don't need to fund themselves with preferred stock.",
        category="Balance Sheet", weight=0.01,
    ))

    # 14. Retained Earnings Growth (no sector adjustment)
    re_0 = _nth(bal, "Retained Earnings", 0)
    re_1 = _nth(bal, "Retained Earnings", 1)
    re_growth = _div(re_0, re_1) if (re_0 is not None and re_1 is not None) else None
    # Compare signed values so shrinking a deficit (−2 → −1) counts as growth and
    # a deepening deficit (−1 → −2) does not pass via a ratio > 1.0.
    re_pass = (re_0 > re_1) if (re_0 is not None and re_1 is not None) else None
    ratios.append(BuffettRatio(
        name="Retained Earnings Growth", value=re_growth, threshold="> 1.0 (growing)",
        passes=re_pass,
        equation="Retained Earnings (Year N) / Retained Earnings (Year N−1)",
        description="Whether retained earnings are growing year-over-year.",
        buffett_logic="Great companies grow retained earnings each year, compounding shareholder wealth.",
        category="Balance Sheet", weight=0.07,
    ))

    # 15. Treasury Stock (no sector adjustment)
    treasury = _latest(bal, "Treasury Stock")
    ratios.append(BuffettRatio(
        name="Treasury Stock", value=treasury, threshold="Exists (non-zero)",
        passes=(treasury is not None and treasury != 0),
        equation="Treasury Stock balance on Balance Sheet",
        description="Whether the company actively repurchases its own shares.",
        buffett_logic="Great companies repurchase their own stock — a sign of confidence and shareholder friendliness.",
        category="Balance Sheet", weight=0.01,
    ))

    # ── Cash Flow ─────────────────────────────────────────────────────────────

    # 16. CapEx Margin
    capex         = _latest(cf, "Capital Expenditure")
    net_income_cf = _latest(cf, "Net Income From Continuing Operations")
    if capex is not None:
        capex = abs(capex)
    cxm = _div(capex, net_income_cf)
    cx_thresh, cx_limit = _sector_threshold(sector, "CapEx Margin")
    ratios.append(BuffettRatio(
        name="CapEx Margin", value=cxm, threshold=cx_thresh,
        passes=(cxm < cx_limit) if cxm is not None else None,
        score=_ramp_low(cxm, cx_limit, cx_limit * 2),
        equation="CapEx / Net Income From Continuing Operations",
        description="Capital expenditure as a percentage of net income.",
        buffett_logic="Great companies don't need heavy equipment investment to sustain their profits.",
        category="Cash Flow", weight=0.06,
    ))

    # Non-ramp metrics (bands, existence checks, hard gates) score 1/0 from pass.
    for r in ratios:
        if r.name not in _RAMP_METRICS:
            r.score = _binary_score(r.passes)

    total_weight = sum(r.weight for r in ratios)
    if abs(total_weight - 1.0) >= 0.001:
        raise ValueError(f"Buffett ratio weights must sum to 1.0, got {total_weight:.4f}")

    return ratios
