"""Technical indicators over plain lists of floats.

Series-returning functions produce a list the same length as the input,
with ``None`` where there is not yet enough data.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

Series = List[Optional[float]]
TRADING_DAYS = 252


def sma(values: Sequence[float], period: int) -> Series:
    if period <= 0:
        raise ValueError("period must be positive")
    out: Series = [None] * len(values)
    window = 0.0
    for i, v in enumerate(values):
        window += v
        if i >= period:
            window -= values[i - period]
        if i >= period - 1:
            out[i] = window / period
    return out


def ema(values: Sequence[Optional[float]], period: int) -> Series:
    """Exponential moving average seeded with the SMA of the first `period` values.

    Leading ``None`` values are skipped, so this can be applied to another indicator.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    out: Series = [None] * len(values)
    start = next((i for i, v in enumerate(values) if v is not None), len(values))
    if len(values) - start < period:
        return out
    k = 2.0 / (period + 1)
    seed_end = start + period
    prev = sum(values[start:seed_end]) / period
    out[seed_end - 1] = prev
    for i in range(seed_end, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(values: Sequence[float], period: int = 14) -> Series:
    """Relative Strength Index using Wilder's smoothing."""
    out: Series = [None] * len(values)
    if len(values) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period + 1, len(values)):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def macd(values: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[Series, Series, Series]:
    """Return (macd line, signal line, histogram)."""
    fast_ema, slow_ema = ema(values, fast), ema(values, slow)
    line: Series = [f - s if f is not None and s is not None else None for f, s in zip(fast_ema, slow_ema)]
    sig = ema(line, signal)
    hist: Series = [m - s if m is not None and s is not None else None for m, s in zip(line, sig)]
    return line, sig, hist


def bollinger(values: Sequence[float], period: int = 20, num_std: float = 2.0) -> Tuple[Series, Series, Series]:
    """Return (lower, middle, upper) Bollinger Bands using population std dev."""
    middle = sma(values, period)
    lower: Series = [None] * len(values)
    upper: Series = [None] * len(values)
    for i, mid in enumerate(middle):
        if mid is None:
            continue
        window = values[i - period + 1 : i + 1]
        std = math.sqrt(sum((v - mid) ** 2 for v in window) / period)
        lower[i], upper[i] = mid - num_std * std, mid + num_std * std
    return lower, middle, upper


def daily_returns(values: Sequence[float]) -> List[float]:
    return [values[i] / values[i - 1] - 1.0 for i in range(1, len(values)) if values[i - 1]]


def total_return(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2 or not values[0]:
        return None
    return values[-1] / values[0] - 1.0


def annualized_volatility(values: Sequence[float], periods_per_year: int = TRADING_DAYS) -> Optional[float]:
    rets = daily_returns(values)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(periods_per_year)


def max_drawdown(values: Sequence[float]) -> Optional[float]:
    """Largest peak-to-trough decline, as a negative fraction (e.g. -0.25)."""
    if not values:
        return None
    peak, worst = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        if peak:
            worst = min(worst, v / peak - 1.0)
    return worst


def sharpe_ratio(values: Sequence[float], risk_free: float = 0.0, periods_per_year: int = TRADING_DAYS) -> Optional[float]:
    rets = daily_returns(values)
    if len(rets) < 2:
        return None
    excess = [r - risk_free / periods_per_year for r in rets]
    mean = sum(excess) / len(excess)
    std = math.sqrt(sum((r - mean) ** 2 for r in excess) / (len(excess) - 1))
    if std == 0:
        return None
    return mean / std * math.sqrt(periods_per_year)


def last(series: Sequence[Optional[float]]) -> Optional[float]:
    return series[-1] if series else None
