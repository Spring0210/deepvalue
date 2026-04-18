from dataclasses import dataclass
from typing import Optional


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


def compute_weighted_score(ratios: list[BuffettRatio]) -> float:
    """
    Weighted score 0-100, normalized to exclude N/A metrics.
    Score = sum(weight for passing) / sum(weight for non-NA) * 100
    """
    passing_weight = sum(r.weight for r in ratios if r.passes is True)
    scored_weight  = sum(r.weight for r in ratios if r.passes is not None)
    if scored_weight == 0:
        return 0.0
    return round(passing_weight / scored_weight * 100, 1)


def compute_ratios(data: dict) -> list[BuffettRatio]:
    fin = data.get("financials", {})
    bal = data.get("balanceSheet", {})
    cf  = data.get("cashflow", {})

    ratios: list[BuffettRatio] = []

    # ── Income Statement ──────────────────────────────────────────────────────

    gross_profit = _latest(fin, "Gross Profit")
    revenue      = _latest(fin, "Total Revenue")
    op_income    = _latest(fin, "Operating Income")

    # 1. Gross Margin — most important moat signal
    gm = _div(gross_profit, revenue)
    ratios.append(BuffettRatio(
        name="Gross Margin", value=gm, threshold="≥ 40%",
        passes=(gm >= 0.40) if gm is not None else None,
        equation="Gross Profit / Total Revenue",
        description="Measures how much revenue remains after direct production costs.",
        buffett_logic="Signals a durable competitive advantage — the company isn't competing on price.",
        category="Income Statement", weight=0.13,
    ))

    # 2. SG&A Margin
    sga  = _latest(fin, "Selling General And Administration")
    sgam = _div(sga, gross_profit)
    ratios.append(BuffettRatio(
        name="SG&A Margin", value=sgam, threshold="≤ 30%",
        passes=(sgam <= 0.30) if sgam is not None else None,
        equation="SG&A Expense / Gross Profit",
        description="Selling, General & Administrative expenses as a share of gross profit.",
        buffett_logic="Wide-moat companies don't need heavy overhead spending to operate.",
        category="Income Statement", weight=0.07,
    ))

    # 3. R&D Margin
    rnd  = _latest(fin, "Research And Development")
    rndm = _div(rnd, gross_profit)
    ratios.append(BuffettRatio(
        name="R&D Margin", value=rndm, threshold="≤ 30%",
        passes=(rndm <= 0.30) if rndm is not None else None,
        equation="R&D Expense / Gross Profit",
        description="Research & Development spending as a share of gross profit.",
        buffett_logic="Heavy R&D dependence means the competitive advantage isn't guaranteed to last.",
        category="Income Statement", weight=0.04,
    ))

    # 4. Depreciation Margin
    dep  = _latest(fin, "Reconciled Depreciation")
    depm = _div(dep, gross_profit)
    ratios.append(BuffettRatio(
        name="Depreciation Margin", value=depm, threshold="≤ 10%",
        passes=(depm <= 0.10) if depm is not None else None,
        equation="Reconciled Depreciation / Gross Profit",
        description="Depreciation & amortization as a share of gross profit.",
        buffett_logic="Great businesses don't need heavy depreciating assets to maintain their competitive edge.",
        category="Income Statement", weight=0.06,
    ))

    # 5. Interest Expense Margin
    interest = _latest(fin, "Interest Expense")
    intm = _div(interest, op_income)
    if intm is not None:
        intm = abs(intm)
    ratios.append(BuffettRatio(
        name="Interest Expense Margin", value=intm, threshold="≤ 15%",
        passes=(intm <= 0.15) if intm is not None else None,
        equation="Interest Expense / Operating Income",
        description="How much of operating income is consumed by interest payments.",
        buffett_logic="Great businesses self-finance with earnings — they don't need much debt.",
        category="Income Statement", weight=0.08,
    ))

    # 6. Effective Tax Rate
    tax    = _latest(fin, "Tax Provision")
    pretax = _latest(fin, "Pretax Income")
    taxr   = _div(tax, pretax)
    ratios.append(BuffettRatio(
        name="Effective Tax Rate", value=taxr, threshold="15% – 30%",
        passes=(0.15 <= taxr <= 0.30) if taxr is not None else None,
        equation="Tax Provision / Pre-Tax Income",
        description="The actual tax rate paid on pre-tax income.",
        buffett_logic="Highly profitable companies pay full taxes — they can't shelter extraordinary income.",
        category="Income Statement", weight=0.05,
    ))

    # 7. Net Profit Margin
    net_income = _latest(fin, "Net Income")
    nm = _div(net_income, revenue)
    ratios.append(BuffettRatio(
        name="Net Profit Margin", value=nm, threshold="≥ 20%",
        passes=(nm >= 0.20) if nm is not None else None,
        equation="Net Income / Total Revenue",
        description="Percentage of revenue that becomes net profit.",
        buffett_logic="Great companies consistently convert 20%+ of revenue into net profit.",
        category="Income Statement", weight=0.11,
    ))

    # 8. EPS Growth (YoY)
    eps_0      = _nth(fin, "Basic EPS", 0)
    eps_1      = _nth(fin, "Basic EPS", 1)
    eps_growth = _div(eps_0, eps_1)
    ratios.append(BuffettRatio(
        name="EPS Growth (YoY)", value=eps_growth, threshold="> 1.0 (positive & growing)",
        passes=(eps_growth > 1.0) if eps_growth is not None else None,
        equation="EPS (Year N) / EPS (Year N−1)",
        description="Year-over-year growth ratio of basic earnings per share.",
        buffett_logic="Great companies grow earnings per share every year without fail.",
        category="Income Statement", weight=0.10,
    ))

    # ── Balance Sheet ─────────────────────────────────────────────────────────

    # 9. Cash vs Current Debt
    cash         = _latest(bal, "Cash And Cash Equivalents")
    current_debt = _latest(bal, "Current Debt")
    cvd = _div(cash, current_debt)
    ratios.append(BuffettRatio(
        name="Cash vs Current Debt", value=cvd, threshold="> 1.0 (cash exceeds debt)",
        passes=(cvd > 1.0) if cvd is not None else None,
        equation="Cash & Equivalents / Current Debt",
        description="Whether the company holds more cash than its near-term debt obligations.",
        buffett_logic="Great companies generate so much cash they hold more than their near-term debt.",
        category="Balance Sheet", weight=0.08,
    ))

    # 10. Adjusted Debt-to-Equity
    total_debt   = _latest(bal, "Total Debt")
    total_assets = _latest(bal, "Total Assets")
    equity_proxy = (total_assets - total_debt) if (total_assets and total_debt) else None
    dte = _div(total_debt, equity_proxy)
    ratios.append(BuffettRatio(
        name="Adj. Debt-to-Equity", value=dte, threshold="< 0.80",
        passes=(dte < 0.80) if dte is not None else None,
        equation="Total Debt / (Total Assets − Total Debt)",
        description="Debt relative to equity (assets minus debt as a proxy for equity).",
        buffett_logic="Great companies fund growth through equity and retained earnings, not debt.",
        category="Balance Sheet", weight=0.09,
    ))

    # 11. Preferred Stock
    preferred = _latest(bal, "Preferred Stock")
    ratios.append(BuffettRatio(
        name="Preferred Stock", value=preferred, threshold="None (= $0)",
        passes=(preferred is None or preferred == 0),
        equation="Preferred Stock balance on Balance Sheet",
        description="Whether the company has issued preferred stock.",
        buffett_logic="Great companies don't need to fund themselves with preferred stock.",
        category="Balance Sheet", weight=0.01,
    ))

    # 12. Retained Earnings Growth
    re_0 = _nth(bal, "Retained Earnings", 0)
    re_1 = _nth(bal, "Retained Earnings", 1)
    re_growth = _div(re_0, re_1) if (re_0 is not None and re_1 is not None) else None
    ratios.append(BuffettRatio(
        name="Retained Earnings Growth", value=re_growth, threshold="> 1.0 (growing)",
        passes=(re_growth > 1.0) if re_growth is not None else None,
        equation="Retained Earnings (Year N) / Retained Earnings (Year N−1)",
        description="Whether retained earnings are growing year-over-year.",
        buffett_logic="Great companies grow retained earnings each year, compounding shareholder wealth.",
        category="Balance Sheet", weight=0.09,
    ))

    # 13. Treasury Stock
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

    # 14. CapEx Margin
    capex         = _latest(cf, "Capital Expenditure")
    net_income_cf = _latest(cf, "Net Income From Continuing Operations")
    if capex is not None:
        capex = abs(capex)
    cxm = _div(capex, net_income_cf)
    ratios.append(BuffettRatio(
        name="CapEx Margin", value=cxm, threshold="< 25%",
        passes=(cxm < 0.25) if cxm is not None else None,
        equation="CapEx / Net Income From Continuing Operations",
        description="Capital expenditure as a percentage of net income.",
        buffett_logic="Great companies don't need heavy equipment investment to sustain their profits.",
        category="Cash Flow", weight=0.08,
    ))

    total_weight = sum(r.weight for r in ratios)
    if abs(total_weight - 1.0) >= 0.001:
        raise ValueError(f"Buffett ratio weights must sum to 1.0, got {total_weight:.4f}")

    return ratios
