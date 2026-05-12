"""First-cut agent tools wrapping the v0.4 domain services.

Each tool has a Pydantic args model (auto-becomes its JSON schema) and an async
handler that returns a plain dict / list — never raw dataclasses, never pandas
objects — so it serializes cleanly into a tool_result block."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent.tools.registry import ToolRegistry
from app.services.buffett import (
    compute_ratios,
    compute_trend_adjustment,
    compute_weighted_score,
)
from app.services.financial import get_price_history, get_stock_data, get_stock_quote
from app.services.moat import compute_moat
from app.services.technicals import compute_technicals
from app.services.valuation import compute_valuation


# ── Args models ───────────────────────────────────────────────────────────────

class TickerArgs(BaseModel):
    ticker: str = Field(
        ...,
        description="Stock ticker symbol. US tickers like 'AAPL'; HK like '0700.HK'; A-shares like '600519.SS'.",
        pattern=r"^[A-Za-z0-9.\-]{1,10}$",
    )


# yfinance accepts a fixed set of period strings; we mirror those here so the
# LLM cannot ask for something nonsensical like "1week" or "ytd".
PeriodLiteral = Literal["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"]


class PriceHistoryArgs(BaseModel):
    ticker: str = Field(..., pattern=r"^[A-Za-z0-9.\-]{1,10}$")
    period: PeriodLiteral = Field(
        default="1y",
        description="Lookback window. Daily bars; periods ≥ 2y use weekly cadence inside the data layer.",
    )


# ── Handlers ──────────────────────────────────────────────────────────────────

async def _get_buffett_score(args: TickerArgs) -> dict[str, Any]:
    ticker = args.ticker.upper()
    quote  = await get_stock_quote(ticker)
    data   = await get_stock_data(ticker)
    sector = quote.get("sector", "")

    ratios     = compute_ratios(data, sector=sector)
    base       = compute_weighted_score(ratios)
    trend_adj  = compute_trend_adjustment(data)
    score      = round(min(100.0, max(0.0, base + trend_adj)), 1)

    # Compact ratio summary — full breakdown would blow up context for the LLM.
    summary = [
        {
            "name":      r.name,
            "value":     r.value,
            "threshold": r.threshold,
            "passes":    r.passes,
            "weight":    r.weight,
        }
        for r in ratios
    ]

    return {
        "ticker":           ticker,
        "name":             quote.get("name"),
        "sector":           sector,
        "industry":         quote.get("industry", ""),
        "weighted_score":   score,
        "trend_adjustment": round(trend_adj, 2),
        "ratios":           summary,
    }


async def _get_stock_quote(args: TickerArgs) -> dict[str, Any]:
    ticker = args.ticker.upper()
    q = await get_stock_quote(ticker)
    # Slim the payload — the agent rarely needs analyst targets etc. in turn 1.
    keep = (
        "name", "price", "change", "changesPercentage", "marketCap", "pe",
        "forwardPE", "pegRatio", "roe", "fcfYield", "revenueGrowth",
        "earningsGrowth", "sector", "industry", "summary", "currency",
        "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
    )
    return {"ticker": ticker, **{k: q.get(k) for k in keep}}


async def _get_valuation(args: TickerArgs) -> dict[str, Any]:
    ticker = args.ticker.upper()
    quote  = await get_stock_quote(ticker)
    data   = await get_stock_data(ticker)
    val    = compute_valuation(quote, data)
    return {"ticker": ticker, **val}


async def _get_moat(args: TickerArgs) -> dict[str, Any]:
    ticker = args.ticker.upper()
    quote  = await get_stock_quote(ticker)
    return {"ticker": ticker, **compute_moat(quote)}


# yfinance period → interval that the existing service layer uses for charts.
# Daily for ≤ 1y, weekly for longer horizons so the series doesn't explode.
_PERIOD_INTERVAL: dict[str, str] = {
    "1mo": "1d", "3mo": "1d", "6mo": "1d", "1y": "1d",
    "2y":  "1wk", "5y": "1wk", "10y": "1wk", "max": "1mo",
}


async def _get_price_history(args: PriceHistoryArgs) -> dict[str, Any]:
    ticker   = args.ticker.upper()
    period   = args.period
    interval = _PERIOD_INTERVAL[period]
    hist     = await get_price_history(ticker, period, interval)

    prices: list[float] = hist.get("prices") or []
    if not prices:
        return {
            "ticker": ticker, "period": period, "interval": interval,
            "n_points": 0, "summary": None,
        }

    first, last  = prices[0], prices[-1]
    period_high  = max(prices)
    period_low   = min(prices)
    total_return = round((last / first - 1) * 100, 2) if first else None
    drawdown_pct = round((last / period_high - 1) * 100, 2) if period_high else None

    return {
        "ticker":    ticker,
        "period":    period,
        "interval":  interval,
        "n_points":  len(prices),
        "summary": {
            "start_price":           round(first, 2),
            "latest_price":          round(last, 2),
            "period_high":           round(period_high, 2),
            "period_low":            round(period_low, 2),
            "total_return_pct":      total_return,
            "drawdown_from_high_pct": drawdown_pct,
        },
    }


async def _get_technicals(args: TickerArgs) -> dict[str, Any]:
    ticker = args.ticker.upper()
    # 1y of daily closes is enough for SMA-200 and RSI-14 to be meaningful.
    hist   = await get_price_history(ticker, "1y", "1d")
    closes = hist.get("prices") or []
    return {"ticker": ticker, **compute_technicals(closes)}


# ── Registration ──────────────────────────────────────────────────────────────

def register_financial_tools(registry: ToolRegistry) -> None:
    registry.register(
        name="get_stock_quote",
        description=(
            "Fetch the current price, market cap, P/E, forward P/E, PEG, ROE, "
            "FCF yield, revenue/earnings growth, sector/industry, business summary, "
            "and 52-week range for a stock ticker. Use this first to understand "
            "what the company does."
        ),
        args_model=TickerArgs,
        handler=_get_stock_quote,
        timeout_s=15.0,
    )
    registry.register(
        name="get_buffett_score",
        description=(
            "Compute the 14-metric Warren-Buffett-style weighted score (0–100) "
            "for a stock, with sector-adjusted thresholds and a trend adjustment "
            "for 3-year improving/deteriorating metrics. Returns the score plus "
            "every ratio's value, threshold, pass/fail, and weight."
        ),
        args_model=TickerArgs,
        handler=_get_buffett_score,
        timeout_s=20.0,
    )
    registry.register(
        name="get_valuation",
        description=(
            "Estimate intrinsic value via four models (Graham Number, 10-year "
            "DCF, FCF-yield value, Greenwald EPV) and report margin of safety "
            "against each. Also returns ROIC, Price/FCF, and a Circle-of-"
            "Competence check flagging hard-to-value businesses."
        ),
        args_model=TickerArgs,
        handler=_get_valuation,
        timeout_s=20.0,
    )
    registry.register(
        name="get_moat",
        description=(
            "Classify the company's competitive moat (Network Effect, Switching "
            "Costs, Cost Advantage, Intangible Assets, or Efficient Scale) and "
            "rate its strength as Wide / Narrow / None, with supporting "
            "indicators drawn from margin, ROE, sector, and growth data."
        ),
        args_model=TickerArgs,
        handler=_get_moat,
        timeout_s=10.0,
    )
    registry.register(
        name="get_price_history",
        description=(
            "Summarize price action over a configurable lookback (1mo–max). "
            "Returns start/latest/high/low, total return %, and drawdown from "
            "period high. Use this to gauge recent momentum without pulling "
            "every bar into context."
        ),
        args_model=PriceHistoryArgs,
        handler=_get_price_history,
        timeout_s=15.0,
    )
    registry.register(
        name="get_technicals",
        description=(
            "Compute technical indicators from 1 year of daily closes: RSI(14), "
            "MACD(12/26/9), SMA-50, SMA-200, price vs each moving average, and "
            "30-day annualized volatility. Useful for momentum / entry timing."
        ),
        args_model=TickerArgs,
        handler=_get_technicals,
        timeout_s=15.0,
    )
