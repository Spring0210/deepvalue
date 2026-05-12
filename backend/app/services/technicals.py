"""Lightweight technical indicators derived from a price series.

Inputs are plain `list[float]` of daily closes so this module stays
pandas-free at the boundary — the caller may use pandas internally if
convenient, but the contract is a list. All outputs are JSON-friendly
scalars so tool results serialize cleanly into Anthropic tool_result
blocks."""

from __future__ import annotations

from typing import Optional


def _ema(values: list[float], window: int) -> list[float]:
    if not values:
        return []
    k = 2 / (window + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(out[-1] + k * (v - out[-1]))
    return out


def rsi(closes: list[float], period: int = 14) -> Optional[float]:
    """Wilder's RSI on the most recent point. Returns None if too few points."""
    if len(closes) <= period:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain  = max(delta, 0.0)
        loss  = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, Optional[float]]:
    if len(closes) < slow + signal:
        return {"macd": None, "signal": None, "histogram": None}
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = _ema(macd_line[slow - 1:], signal)
    m = round(macd_line[-1], 4)
    s = round(signal_line[-1], 4)
    return {"macd": m, "signal": s, "histogram": round(m - s, 4)}


def sma(closes: list[float], window: int) -> Optional[float]:
    if len(closes) < window:
        return None
    return round(sum(closes[-window:]) / window, 2)


def volatility_pct(closes: list[float], window: int = 30) -> Optional[float]:
    """Annualized stdev of daily returns over the trailing window (% units)."""
    if len(closes) < window + 1:
        return None
    rets = [(closes[i] / closes[i - 1] - 1) for i in range(len(closes) - window, len(closes))]
    if not rets:
        return None
    mean = sum(rets) / len(rets)
    var  = sum((r - mean) ** 2 for r in rets) / max(len(rets) - 1, 1)
    daily_std = var ** 0.5
    return round(daily_std * (252 ** 0.5) * 100, 2)


def compute_technicals(closes: list[float]) -> dict:
    """Compute the full indicator bundle. Empty fields are None, not omitted."""
    if not closes:
        return {
            "rsi_14": None, "macd": {"macd": None, "signal": None, "histogram": None},
            "sma_50": None, "sma_200": None,
            "price": None,
            "price_vs_sma50_pct": None, "price_vs_sma200_pct": None,
            "volatility_30d_annualized_pct": None,
        }

    price   = closes[-1]
    sma_50  = sma(closes, 50)
    sma_200 = sma(closes, 200)

    def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
        if a is None or b is None or b == 0:
            return None
        return round((a / b - 1) * 100, 2)

    return {
        "rsi_14":   rsi(closes, 14),
        "macd":     macd(closes),
        "sma_50":   sma_50,
        "sma_200":  sma_200,
        "price":    round(price, 2),
        "price_vs_sma50_pct":  _pct(price, sma_50),
        "price_vs_sma200_pct": _pct(price, sma_200),
        "volatility_30d_annualized_pct": volatility_pct(closes, 30),
    }
