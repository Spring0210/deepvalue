import asyncio
from threading import Lock
from typing import Optional

import pandas as pd
import yfinance as yf
from cachetools import TTLCache, cached

_QUOTE_CACHE:   TTLCache = TTLCache(maxsize=64,  ttl=900)   # 15-minute TTL
_DATA_CACHE:    TTLCache = TTLCache(maxsize=64,  ttl=900)
_HISTORY_CACHE: TTLCache = TTLCache(maxsize=128, ttl=1800)  # 30-minute TTL
_QUOTE_LOCK   = Lock()
_DATA_LOCK    = Lock()
_HISTORY_LOCK = Lock()


def _df_to_dict(df: pd.DataFrame) -> dict:
    """Convert yfinance DataFrame (index=fields, columns=dates) to {date_str: {field: value}}."""
    result: dict = {}
    for col in df.columns:
        date_str = str(col.date())
        result[date_str] = {
            field: (None if pd.isna(val) else float(val))
            for field, val in df[col].items()
        }
    return result


@cached(cache=_QUOTE_CACHE, lock=_QUOTE_LOCK)
def _fetch_quote_sync(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not price:
        raise ValueError(f"No quote data found for '{ticker}'. Check the ticker symbol.")

    prev_close = info.get("previousClose") or price
    change = price - prev_close
    change_pct = (change / prev_close * 100) if prev_close else None

    market_cap = info.get("marketCap")
    fcf        = info.get("freeCashflow")
    fcf_yield  = (fcf / market_cap) if (fcf and market_cap) else None

    summary = info.get("longBusinessSummary", "")
    if len(summary) > 300:
        summary = summary[:297] + "…"

    return {
        "name":              info.get("longName") or info.get("shortName", ticker),
        "price":             price,
        "change":            change,
        "changesPercentage": change_pct,
        "marketCap":         market_cap,
        "pe":                info.get("trailingPE"),
        "exchange":          info.get("exchange", ""),
        "sector":            info.get("sector", ""),
        "industry":          info.get("industry", ""),
        "summary":           summary,
        "forwardPE":         info.get("forwardPE"),
        "pegRatio":          info.get("pegRatio"),
        "roe":               info.get("returnOnEquity"),
        "roa":               info.get("returnOnAssets"),
        "revenueGrowth":     info.get("revenueGrowth"),
        "earningsGrowth":    info.get("earningsGrowth"),
        "fcfYield":          fcf_yield,
        "freeCashflow":      fcf,
        "dividendYield":     info.get("dividendYield"),
        "grossMargins":      info.get("grossMargins"),
        "operatingMargins":  info.get("operatingMargins"),
        "evToEbitda":        info.get("enterpriseToEbitda"),
        # 52-week range + analyst consensus
        "fiftyTwoWeekHigh":        info.get("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow":         info.get("fiftyTwoWeekLow"),
        "targetLowPrice":          info.get("targetLowPrice"),
        "targetMeanPrice":         info.get("targetMeanPrice"),
        "targetMedianPrice":       info.get("targetMedianPrice"),
        "targetHighPrice":         info.get("targetHighPrice"),
        "recommendationKey":       info.get("recommendationKey"),
        "numberOfAnalystOpinions": info.get("numberOfAnalystOpinions"),
        "heldPercentInsiders":     info.get("heldPercentInsiders"),
        # Valuation inputs
        "trailingEps":             info.get("trailingEps"),
        "bookValue":               info.get("bookValue"),
        "sharesOutstanding":       info.get("sharesOutstanding"),
    }


@cached(cache=_DATA_CACHE, lock=_DATA_LOCK)
def _fetch_data_sync(ticker: str) -> dict:
    t = yf.Ticker(ticker)

    try:
        income   = t.financials
        balance  = t.balance_sheet
        cashflow = t.cashflow
    except Exception as exc:
        raise ValueError(f"Failed to fetch data for '{ticker}': {exc}") from exc

    if income is None or income.empty:
        raise ValueError(
            f"No financial data found for '{ticker}'. "
            "Check that the ticker is valid (e.g. AAPL, MSFT, KO, 0700.HK, 600519.SS)."
        )

    return {
        "financials":   _df_to_dict(income),
        "balanceSheet": _df_to_dict(balance),
        "cashflow":     _df_to_dict(cashflow),
    }


@cached(cache=_HISTORY_CACHE, lock=_HISTORY_LOCK)
def _fetch_history_sync(ticker: str, period: str, interval: str) -> dict:
    t = yf.Ticker(ticker)
    hist = t.history(period=period, interval=interval)
    if hist.empty:
        return {"dates": [], "prices": [], "volumes": [], "is_intraday": False}
    is_intraday = interval in ("1m", "2m", "5m", "15m", "30m", "1h")
    dates = []
    for idx in hist.index:
        if is_intraday:
            dates.append(idx.strftime("%Y-%m-%d %H:%M"))
        else:
            dates.append(str(idx.date()))
    return {
        "dates":       dates,
        "prices":      [round(float(p), 2) for p in hist["Close"].tolist()],
        "volumes":     [int(v) for v in hist["Volume"].tolist()],
        "is_intraday": is_intraday,
    }


async def get_stock_quote(ticker: str) -> dict:
    return await asyncio.to_thread(_fetch_quote_sync, ticker)


async def get_stock_data(ticker: str) -> dict:
    return await asyncio.to_thread(_fetch_data_sync, ticker)


async def get_price_history(ticker: str, period: str = "1y", interval: str = "1d") -> dict:
    return await asyncio.to_thread(_fetch_history_sync, ticker, period, interval)


def safe_get(statement: dict, column: str, row: str) -> Optional[float]:
    return statement.get(column, {}).get(row)
