from statistics import mean, pstdev
from typing import Optional

from app.services.valuation import compute_roic

# The only quantitative moat proof Buffett and Munger endorse: a business that
# earns returns on capital above its cost, year after year. A wide moat is what
# *defends* that spread — so we measure ROIC persistence and margin stability
# from the statements rather than inferring a moat from sector + multiple.
_ROIC_HURDLE = 0.12
_MARGIN_CV_STABLE = 0.15   # gross-margin coefficient of variation under 15% = stable


def _book_equity_year(row: dict) -> Optional[float]:
    for field in ("Stockholders Equity", "Common Stock Equity",
                  "Total Equity Gross Minority Interest"):
        if row.get(field) is not None:
            return row.get(field)
    return None


def _moat_evidence(data: Optional[dict]) -> Optional[dict]:
    """Multi-year ROIC series and gross-margin stability from the statements.
    Returns None when there isn't enough data to judge."""
    fin = (data or {}).get("financials", {})
    bal = (data or {}).get("balanceSheet", {})
    if not fin:
        return None

    roic_series: list[float] = []
    margins: list[float] = []
    for yr, row in fin.items():
        b = bal.get(yr, {})
        pre = row.get("Pretax Income")
        tax = row.get("Tax Provision")
        rate = (tax / pre) if (tax and pre and pre > 0) else None
        r = compute_roic(
            row.get("Operating Income"), rate, b.get("Total Debt"),
            _book_equity_year(b), b.get("Cash And Cash Equivalents"),
        )
        if r is not None:
            roic_series.append(r)

        gp, rev = row.get("Gross Profit"), row.get("Total Revenue")
        if gp is not None and rev:
            margins.append(gp / rev)

    if not roic_series:
        return None

    avg_roic = mean(roic_series)
    persistence = sum(1 for r in roic_series if r >= _ROIC_HURDLE) / len(roic_series)
    margin_cv = (pstdev(margins) / mean(margins)) if (len(margins) >= 2 and mean(margins) > 0) else None
    margin_stable = margin_cv is not None and margin_cv < _MARGIN_CV_STABLE

    return {
        "roic_series":   [round(r, 4) for r in roic_series],
        "avg_roic":      avg_roic,
        "persistence":   persistence,
        "margin_cv":     margin_cv,
        "margin_stable": margin_stable,
        "years":         len(roic_series),
    }


def _strength_from_evidence(ev: dict) -> str:
    if ev["years"] >= 3 and ev["persistence"] >= 0.8 and ev["avg_roic"] >= _ROIC_HURDLE and ev["margin_stable"]:
        return "Wide"
    if ev["persistence"] >= 0.5 or ev["avg_roic"] >= 0.10:
        return "Narrow"
    return "None"


def _evidence_indicators(ev: dict) -> list[str]:
    out = [
        f"ROIC averaged {ev['avg_roic'] * 100:.0f}% over {ev['years']} yrs "
        f"({ev['persistence'] * 100:.0f}% of years ≥ {_ROIC_HURDLE * 100:.0f}%)",
    ]
    if ev["margin_cv"] is not None:
        word = "stable" if ev["margin_stable"] else "volatile"
        out.append(f"Gross margin {word} (CV {ev['margin_cv'] * 100:.0f}%)")
    return out


def _score_network_effect(sector: str, gross_margin: float, rev_growth: float, market_cap: float) -> float:
    score = 0.0
    if sector in ('Technology', 'Communication Services'):
        score += 0.30
    if gross_margin > 0.65:
        score += 0.35
    elif gross_margin > 0.50:
        score += 0.20
    elif gross_margin > 0.40:
        score += 0.10
    if rev_growth > 0.25:
        score += 0.25
    elif rev_growth > 0.15:
        score += 0.15
    elif rev_growth > 0.08:
        score += 0.05
    if market_cap > 200e9:
        score += 0.10
    return min(score, 1.0)


def _score_switching_costs(sector: str, gross_margin: float, op_margin: float, rev_growth: float) -> float:
    score = 0.0
    if sector in ('Technology', 'Financials', 'Healthcare'):
        score += 0.25
    if gross_margin > 0.55:
        score += 0.30
    elif gross_margin > 0.40:
        score += 0.15
    if op_margin > 0.25:
        score += 0.25
    elif op_margin > 0.15:
        score += 0.15
    if 0.04 <= rev_growth <= 0.25:
        score += 0.20
    return min(score, 1.0)


def _score_cost_advantage(sector: str, gross_margin: float, roe: float, market_cap: float) -> float:
    score = 0.0
    if sector in ('Consumer Staples', 'Industrials', 'Energy', 'Materials'):
        score += 0.30
    if 0.20 <= gross_margin <= 0.55:
        score += 0.20
    if roe > 0.20:
        score += 0.30
    elif roe > 0.12:
        score += 0.15
    if market_cap > 30e9:
        score += 0.20
    return min(score, 1.0)


def _score_intangible_assets(sector: str, gross_margin: float, roe: float, op_margin: float) -> float:
    # P/E was previously an input here — dropped: a premium multiple is the
    # market pricing in a moat, not evidence of one. Use pricing power (margins).
    score = 0.0
    if sector in ('Consumer Staples', 'Healthcare', 'Consumer Discretionary'):
        score += 0.25
    if gross_margin > 0.50:
        score += 0.30
    elif gross_margin > 0.35:
        score += 0.15
    if roe > 0.25:
        score += 0.25
    elif roe > 0.15:
        score += 0.15
    if op_margin > 0.25:
        score += 0.20
    elif op_margin > 0.18:
        score += 0.10
    return min(score, 1.0)


def _score_efficient_scale(sector: str, dividend_yield: float, rev_growth: float, op_margin: float) -> float:
    score = 0.0
    if sector in ('Utilities', 'Real Estate'):
        score += 0.45
    elif sector in ('Energy', 'Communication Services'):
        score += 0.20
    if dividend_yield and dividend_yield > 0.03:
        score += 0.25
    elif dividend_yield and dividend_yield > 0.015:
        score += 0.12
    if -0.02 <= rev_growth <= 0.07:
        score += 0.20
    if op_margin > 0.15:
        score += 0.10
    return min(score, 1.0)


def _get_indicators(moat_type: str, quote: dict) -> list[str]:
    gross_margin  = (quote.get('grossMargins') or 0) * 100
    op_margin     = (quote.get('operatingMargins') or 0) * 100
    roe           = (quote.get('roe') or 0) * 100
    rev_growth    = (quote.get('revenueGrowth') or 0) * 100
    dividend_yield = (quote.get('dividendYield') or 0) * 100
    sector        = quote.get('sector', '') or ''
    market_cap    = quote.get('marketCap') or 0

    indicators: list[str] = []

    if moat_type == 'Network Effect':
        if sector:
            indicators.append(f"Sector: {sector}")
        if gross_margin > 40:
            indicators.append(f"Gross margin {gross_margin:.0f}% (software-like economics)")
        if rev_growth > 0:
            indicators.append(f"Revenue growth {rev_growth:.0f}%")
        if market_cap > 50e9:
            indicators.append(f"Scale: ${market_cap / 1e9:.0f}B market cap")

    elif moat_type == 'Switching Costs':
        if gross_margin > 0:
            indicators.append(f"Gross margin {gross_margin:.0f}% suggests recurring revenue")
        if op_margin > 0:
            indicators.append(f"Operating margin {op_margin:.0f}%")
        if rev_growth > 0:
            indicators.append(f"Consistent revenue growth {rev_growth:.0f}%")
        if sector:
            indicators.append(f"Sector: {sector}")

    elif moat_type == 'Cost Advantage':
        if roe > 0:
            indicators.append(f"ROE {roe:.0f}% from operational efficiency")
        if gross_margin > 0:
            indicators.append(f"Gross margin {gross_margin:.0f}%")
        if market_cap > 0:
            indicators.append(f"Scale: ${market_cap / 1e9:.0f}B market cap")
        if sector:
            indicators.append(f"Sector: {sector}")

    elif moat_type == 'Intangible Assets':
        if gross_margin > 0:
            indicators.append(f"Gross margin {gross_margin:.0f}% reflects brand pricing power")
        if roe > 0:
            indicators.append(f"ROE {roe:.0f}% driven by intangibles")
        if op_margin > 0:
            indicators.append(f"Operating margin {op_margin:.0f}%")
        if sector:
            indicators.append(f"Sector: {sector}")

    elif moat_type == 'Efficient Scale':
        if sector:
            indicators.append(f"Sector: {sector}")
        if dividend_yield > 0:
            indicators.append(f"Dividend yield {dividend_yield:.1f}%")
        if rev_growth >= -5:
            indicators.append(f"Stable revenue growth {rev_growth:.0f}%")
        if op_margin > 0:
            indicators.append(f"Operating margin {op_margin:.0f}%")

    return indicators[:4]


def compute_moat(quote: dict, data: Optional[dict] = None) -> dict:
    sector        = quote.get('sector', '') or ''
    gross_margin  = quote.get('grossMargins') or 0
    op_margin     = quote.get('operatingMargins') or 0
    roe           = quote.get('roe') or 0
    rev_growth    = quote.get('revenueGrowth') or 0
    market_cap    = quote.get('marketCap') or 0
    dividend_yield = quote.get('dividendYield') or 0

    # The five type scores still narrate *what kind* of moat the business has.
    scores = {
        'Network Effect':    _score_network_effect(sector, gross_margin, rev_growth, market_cap),
        'Switching Costs':   _score_switching_costs(sector, gross_margin, op_margin, rev_growth),
        'Cost Advantage':    _score_cost_advantage(sector, gross_margin, roe, market_cap),
        'Intangible Assets': _score_intangible_assets(sector, gross_margin, roe, op_margin),
        'Efficient Scale':   _score_efficient_scale(sector, dividend_yield, rev_growth, op_margin),
    }

    primary       = max(scores, key=scores.__getitem__)
    primary_score = scores[primary]
    primary_type  = primary if primary_score >= 0.30 else None

    # Strength is decided by evidence (ROIC persistence + margin stability) when
    # statements are available; otherwise fall back to a single-period quality gate.
    evidence = _moat_evidence(data)
    if evidence is not None:
        strength   = _strength_from_evidence(evidence)
        indicators = _evidence_indicators(evidence) + _get_indicators(primary_type or '', quote)
        indicators = indicators[:4]
    else:
        quality_count = sum([
            gross_margin > 0.40,
            roe > 0.15,
            op_margin > 0.15,
        ])
        if primary_score >= 0.55 and quality_count >= 2:
            strength = 'Wide'
        elif primary_score >= 0.35 or quality_count >= 1:
            strength = 'Narrow'
        else:
            strength = 'None'
        indicators = _get_indicators(primary_type or '', quote)

    return {
        'strength':     strength,
        'primary_type': primary_type,
        'scores':       {k: round(v, 3) for k, v in scores.items()},
        'indicators':   indicators,
    }
