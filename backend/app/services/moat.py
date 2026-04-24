from typing import Optional


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


def _score_intangible_assets(sector: str, gross_margin: float, roe: float, pe: float) -> float:
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
    if pe and pe > 25:
        score += 0.20
    elif pe and pe > 18:
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
    pe            = quote.get('pe') or 0
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
        if pe > 0:
            indicators.append(f"P/E {pe:.0f}x premium valuation")
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


def compute_moat(quote: dict) -> dict:
    sector        = quote.get('sector', '') or ''
    gross_margin  = quote.get('grossMargins') or 0
    op_margin     = quote.get('operatingMargins') or 0
    roe           = quote.get('roe') or 0
    rev_growth    = quote.get('revenueGrowth') or 0
    pe            = quote.get('pe') or 0
    market_cap    = quote.get('marketCap') or 0
    dividend_yield = quote.get('dividendYield') or 0

    scores = {
        'Network Effect':    _score_network_effect(sector, gross_margin, rev_growth, market_cap),
        'Switching Costs':   _score_switching_costs(sector, gross_margin, op_margin, rev_growth),
        'Cost Advantage':    _score_cost_advantage(sector, gross_margin, roe, market_cap),
        'Intangible Assets': _score_intangible_assets(sector, gross_margin, roe, pe),
        'Efficient Scale':   _score_efficient_scale(sector, dividend_yield, rev_growth, op_margin),
    }

    primary       = max(scores, key=scores.__getitem__)
    primary_score = scores[primary]

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

    primary_type = primary if primary_score >= 0.30 else None
    indicators   = _get_indicators(primary_type or '', quote)

    return {
        'strength':     strength,
        'primary_type': primary_type,
        'scores':       {k: round(v, 3) for k, v in scores.items()},
        'indicators':   indicators,
    }
