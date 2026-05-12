"""Boundary-first tests for the technicals service.

Real returns/RSI/MACD math is library-grade; we mostly want to confirm:
 - empty / too-short inputs return None, not raise
 - shapes match what the agent tool consumes
 - sign / magnitude is correct on trivially monotonic series"""

from __future__ import annotations

from app.services.technicals import (
    compute_technicals, macd, rsi, sma, volatility_pct,
)


# ── rsi ───────────────────────────────────────────────────────────────────────

def test_rsi_returns_none_when_too_short():
    assert rsi([1.0, 2.0, 3.0], period=14) is None


def test_rsi_monotonic_up_pins_to_100():
    closes = [float(i) for i in range(1, 50)]
    assert rsi(closes, period=14) == 100.0


def test_rsi_monotonic_down_pins_to_0():
    closes = [float(i) for i in range(50, 0, -1)]
    assert rsi(closes, period=14) == 0.0


def test_rsi_mixed_series_in_range():
    closes = [100 + (i % 5) - 2 for i in range(80)]
    value = rsi(closes, period=14)
    assert value is not None and 0.0 <= value <= 100.0


# ── macd ──────────────────────────────────────────────────────────────────────

def test_macd_returns_nones_when_too_short():
    out = macd([1.0] * 10)
    assert out == {"macd": None, "signal": None, "histogram": None}


def test_macd_shape_on_long_series():
    out = macd([float(i) for i in range(200)])
    assert set(out.keys()) == {"macd", "signal", "histogram"}
    assert all(isinstance(v, float) for v in out.values())


# ── sma + volatility ──────────────────────────────────────────────────────────

def test_sma_returns_none_when_too_short():
    assert sma([1.0, 2.0], window=50) is None


def test_sma_of_constant_series_equals_value():
    assert sma([10.0] * 60, window=50) == 10.0


def test_volatility_zero_for_flat_series():
    out = volatility_pct([100.0] * 60, window=30)
    assert out == 0.0


def test_volatility_positive_for_noisy_series():
    closes = [100.0 + (-1) ** i * 0.5 for i in range(60)]
    out = volatility_pct(closes, window=30)
    assert out is not None and out > 0


# ── compute_technicals end-to-end ─────────────────────────────────────────────

def test_compute_technicals_handles_empty_input():
    out = compute_technicals([])
    assert out["price"] is None
    assert out["rsi_14"] is None
    assert out["macd"] == {"macd": None, "signal": None, "histogram": None}


def test_compute_technicals_full_payload_keys():
    closes = [100.0 + (i * 0.1) for i in range(260)]
    out = compute_technicals(closes)
    expected_keys = {
        "rsi_14", "macd", "sma_50", "sma_200", "price",
        "price_vs_sma50_pct", "price_vs_sma200_pct",
        "volatility_30d_annualized_pct",
    }
    assert expected_keys.issubset(out.keys())
    assert out["price"] == round(closes[-1], 2)
    # On a steady uptrend price should sit above both MAs.
    assert out["price_vs_sma50_pct"] > 0
    assert out["price_vs_sma200_pct"] > 0
