"""First-cut agent tools wrapping the v0.4 domain services.

Each tool has a Pydantic args model (auto-becomes its JSON schema) and an async
handler that returns a plain dict / list — never raw dataclasses, never pandas
objects — so it serializes cleanly into a tool_result block."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent.tools.registry import ToolRegistry
from app.services.buffett import (
    compute_ratios,
    compute_trend_adjustment,
    compute_weighted_score,
)
from app.services.financial import get_stock_data, get_stock_quote


class TickerArgs(BaseModel):
    ticker: str = Field(
        ...,
        description="Stock ticker symbol. US tickers like 'AAPL'; HK like '0700.HK'; A-shares like '600519.SS'.",
        pattern=r"^[A-Za-z0-9.\-]{1,10}$",
    )


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
