import asyncio
from threading import Lock
from typing import Optional

import pandas as pd
import yfinance as yf
from cachetools import TTLCache, cached

_QUOTE_CACHE:     TTLCache = TTLCache(maxsize=64,  ttl=900)   # 15-minute TTL
_DATA_CACHE:      TTLCache = TTLCache(maxsize=64,  ttl=900)
_QUARTERLY_CACHE: TTLCache = TTLCache(maxsize=64,  ttl=900)
_HISTORY_CACHE:   TTLCache = TTLCache(maxsize=128, ttl=1800)  # 30-minute TTL
_QUOTE_LOCK     = Lock()
_DATA_LOCK      = Lock()
_QUARTERLY_LOCK = Lock()
_HISTORY_LOCK   = Lock()

TTM_LABEL = "TTM"

# yfinance labels equity differently across tickers; try the common fields in order.
_EQUITY_FIELDS = (
    "Stockholders Equity",
    "Common Stock Equity",
    "Total Equity Gross Minority Interest",
)


def _normalize_dividend_yield(raw: Optional[float]) -> Optional[float]:
    """yfinance returns the dividend yield in percent (e.g. 2.68 = 2.68%); the
    rest of the app treats it as a fraction. Normalize to a fraction so PEG/PEGY,
    the moat score, and the overview display are all consistent."""
    if raw is None:
        return None
    return raw / 100


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
        "dividendYield":     _normalize_dividend_yield(info.get("dividendYield")),
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
        "beta":                    info.get("beta"),
        # Currency
        "currency":                info.get("currency", "USD"),
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


@cached(cache=_QUARTERLY_CACHE, lock=_QUARTERLY_LOCK)
def _fetch_quarterly_sync(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    try:
        income   = t.quarterly_financials
        balance  = t.quarterly_balance_sheet
        cashflow = t.quarterly_cashflow
    except Exception:
        return {"financials": {}, "balanceSheet": {}, "cashflow": {}}
    return {
        "financials":   _df_to_dict(income)   if income   is not None else {},
        "balanceSheet": _df_to_dict(balance)  if balance  is not None else {},
        "cashflow":     _df_to_dict(cashflow) if cashflow is not None else {},
    }


def _book_equity_col(col: dict) -> Optional[float]:
    for field in _EQUITY_FIELDS:
        if col.get(field) is not None:
            return col.get(field)
    return None


def _sum_quarters(statement: dict, n: int = 4) -> Optional[dict]:
    """Sum the n most-recent quarterly columns field-by-field (TTM). Returns None
    if fewer than n quarters exist; a field present in only some quarters is None
    rather than understated by a partial sum."""
    cols = list(statement.keys())[:n]
    if len(cols) < n:
        return None
    fields: set = set()
    for c in cols:
        fields.update(statement[c].keys())
    out: dict = {}
    for f in fields:
        vals = [statement[c].get(f) for c in cols]
        out[f] = sum(vals) if all(v is not None for v in vals) else None
    return out


def _inject_avg_capital(mrq: dict, year_ago: Optional[dict]) -> None:
    """Add trailing-year-average invested-capital inputs to the MRQ column.
    Averages the most-recent quarter with the year-ago quarter; falls back to the
    ending (MRQ) value when the year-ago quarter is unavailable."""
    def avg(a: Optional[float], b: Optional[float]) -> Optional[float]:
        if a is not None and b is not None:
            return (a + b) / 2
        return a

    mrq["_TTM Avg Total Debt"] = avg(mrq.get("Total Debt"),
                                     year_ago.get("Total Debt") if year_ago else None)
    mrq["_TTM Avg Cash"] = avg(mrq.get("Cash And Cash Equivalents"),
                               year_ago.get("Cash And Cash Equivalents") if year_ago else None)
    mrq["_TTM Avg Equity"] = avg(_book_equity_col(mrq),
                                 _book_equity_col(year_ago) if year_ago else None)


def build_ttm_data(annual: dict, quarterly: dict) -> dict:
    """Normalize statements to TTM income/cashflow + MRQ balance, keeping the
    annual columns behind them for multi-year trend and growth. Falls back to the
    annual data unchanged when there aren't four quarters to roll up."""
    ttm_income = _sum_quarters(quarterly.get("financials", {}), 4)
    if ttm_income is None:
        return annual   # not enough quarterly history → annual fallback

    fin = {TTM_LABEL: ttm_income, **annual.get("financials", {})}

    ttm_cf = _sum_quarters(quarterly.get("cashflow", {}), 4)
    cf = {TTM_LABEL: ttm_cf, **annual.get("cashflow", {})} if ttm_cf is not None \
        else annual.get("cashflow", {})

    q_bal = quarterly.get("balanceSheet", {})
    bal_cols = list(q_bal.keys())
    mrq = dict(q_bal[bal_cols[0]]) if bal_cols else {}
    year_ago = q_bal[bal_cols[4]] if len(bal_cols) >= 5 else None
    _inject_avg_capital(mrq, year_ago)
    bal = {TTM_LABEL: mrq, **annual.get("balanceSheet", {})}

    return {"financials": fin, "balanceSheet": bal, "cashflow": cf}


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
    annual = await asyncio.to_thread(_fetch_data_sync, ticker)
    try:
        quarterly = await asyncio.to_thread(_fetch_quarterly_sync, ticker)
    except Exception:
        quarterly = {"financials": {}, "balanceSheet": {}, "cashflow": {}}
    return build_ttm_data(annual, quarterly)


async def get_price_history(ticker: str, period: str = "1y", interval: str = "1d") -> dict:
    return await asyncio.to_thread(_fetch_history_sync, ticker, period, interval)


def safe_get(statement: dict, column: str, row: str) -> Optional[float]:
    return statement.get(column, {}).get(row)
