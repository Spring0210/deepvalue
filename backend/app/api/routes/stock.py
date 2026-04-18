import re
from dataclasses import asdict
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.financial import get_stock_data, get_stock_quote, get_price_history
from app.services.buffett import compute_ratios, compute_weighted_score
from app.services.rag import stream_recommendation
from app.services.valuation import compute_valuation

router = APIRouter()

_TICKER_RE = re.compile(r'^[A-Z0-9.\-]{1,10}$')


def _validate_ticker(ticker: str) -> str:
    t = ticker.upper()
    if not _TICKER_RE.match(t):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol.")
    return t


@router.get("/{ticker}/quote")
async def get_quote(ticker: str):
    ticker = _validate_ticker(ticker)
    try:
        return await get_stock_quote(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{ticker}/financials")
async def get_financials(ticker: str):
    ticker = _validate_ticker(ticker)
    try:
        return await get_stock_data(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{ticker}/ratios")
async def get_ratios(ticker: str):
    ticker = _validate_ticker(ticker)
    try:
        data   = await get_stock_data(ticker)
        ratios = compute_ratios(data)
        score  = compute_weighted_score(ratios)
        return {
            "ticker":         ticker,
            "ratios":         [asdict(r) for r in ratios],
            "weighted_score": score,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


_PERIOD_INTERVAL: dict[str, str] = {
    "1d":  "5m",
    "5d":  "15m",
    "1mo": "1d",
    "3mo": "1d",
    "6mo": "1d",
    "1y":  "1d",
    "2y":  "1wk",
    "5y":  "1wk",
}

@router.get("/{ticker}/history")
async def get_history(ticker: str, period: str = "1y"):
    ticker = _validate_ticker(ticker)
    if period not in _PERIOD_INTERVAL:
        raise HTTPException(status_code=400, detail=f"Invalid period. Use one of: {', '.join(_PERIOD_INTERVAL)}")
    try:
        return await get_price_history(ticker, period, _PERIOD_INTERVAL[period])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{ticker}/valuation")
async def get_valuation(ticker: str):
    ticker = _validate_ticker(ticker)
    try:
        quote = await get_stock_quote(ticker)
        return compute_valuation(quote)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class RecommendationRequest(BaseModel):
    ticker: str
    ratios: list[dict]
    weighted_score: float
    quote: dict


@router.post("/recommendation")
def get_recommendation(req: RecommendationRequest):
    """Stream an AI-generated investment recommendation based on Buffett metrics."""
    ticker = _validate_ticker(req.ticker)
    return StreamingResponse(
        stream_recommendation(ticker, req.ratios, req.weighted_score, req.quote),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
