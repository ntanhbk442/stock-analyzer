"""Build analysis summaries and trading signals from a price history."""

from __future__ import annotations

from typing import Dict, List, Optional

from . import indicators as ind
from .data import PriceHistory


def summarize(history: PriceHistory) -> Dict:
    closes = history.closes
    bars = history.bars
    first, latest = bars[0], bars[-1]
    prev_close = bars[-2].close if len(bars) > 1 else None

    macd_line, macd_signal, macd_hist = ind.macd(closes)
    bb_lower, bb_mid, bb_upper = ind.bollinger(closes)

    summary = {
        "symbol": history.symbol,
        "currency": history.currency,
        "start": first.date.isoformat(),
        "end": latest.date.isoformat(),
        "bars": len(bars),
        "close": latest.close,
        "change": latest.close - prev_close if prev_close is not None else None,
        "change_pct": latest.close / prev_close - 1.0 if prev_close else None,
        "period_high": max(b.high for b in bars),
        "period_low": min(b.low for b in bars),
        "avg_volume": sum(b.volume for b in bars) / len(bars),
        "total_return": ind.total_return(closes),
        "volatility": ind.annualized_volatility(closes),
        "sharpe": ind.sharpe_ratio(closes),
        "max_drawdown": ind.max_drawdown(closes),
        "sma20": ind.last(ind.sma(closes, 20)),
        "sma50": ind.last(ind.sma(closes, 50)),
        "sma200": ind.last(ind.sma(closes, 200)),
        "ema12": ind.last(ind.ema(closes, 12)),
        "ema26": ind.last(ind.ema(closes, 26)),
        "rsi14": ind.last(ind.rsi(closes, 14)),
        "macd": ind.last(macd_line),
        "macd_signal": ind.last(macd_signal),
        "macd_hist": ind.last(macd_hist),
        "bb_lower": ind.last(bb_lower),
        "bb_middle": ind.last(bb_mid),
        "bb_upper": ind.last(bb_upper),
    }
    summary["signals"] = signals(summary)
    return summary


def signals(s: Dict) -> List[str]:
    """Plain-language readings of the indicators. Informational, not advice."""
    out: List[str] = []
    close = s["close"]

    sma50, sma200 = s.get("sma50"), s.get("sma200")
    if sma50 is not None and sma200 is not None:
        if sma50 > sma200:
            out.append("Bullish trend: 50-day SMA is above 200-day SMA (golden cross regime)")
        else:
            out.append("Bearish trend: 50-day SMA is below 200-day SMA (death cross regime)")
    for key, label in (("sma50", "50-day"), ("sma200", "200-day")):
        value = s.get(key)
        if value is not None:
            side = "above" if close >= value else "below"
            out.append(f"Price is {side} its {label} SMA ({_pct(close / value - 1.0)})")

    rsi = s.get("rsi14")
    if rsi is not None:
        if rsi >= 70:
            out.append(f"RSI {rsi:.1f}: overbought")
        elif rsi <= 30:
            out.append(f"RSI {rsi:.1f}: oversold")
        else:
            out.append(f"RSI {rsi:.1f}: neutral")

    hist = s.get("macd_hist")
    if hist is not None:
        momentum = "bullish" if hist > 0 else "bearish"
        out.append(f"MACD is {'above' if hist > 0 else 'below'} its signal line ({momentum} momentum)")

    lower, upper = s.get("bb_lower"), s.get("bb_upper")
    if lower is not None and upper is not None:
        if close > upper:
            out.append("Price is above the upper Bollinger Band (stretched to the upside)")
        elif close < lower:
            out.append("Price is below the lower Bollinger Band (stretched to the downside)")
    return out


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value * 100:+.2f}%"


def indicator_rows(history: PriceHistory) -> List[Dict]:
    """Per-bar rows of price plus common indicators."""
    closes = history.closes
    sma20, sma50 = ind.sma(closes, 20), ind.sma(closes, 50)
    rsi14 = ind.rsi(closes, 14)
    macd_line, macd_signal, _ = ind.macd(closes)
    rows = []
    for i, bar in enumerate(history.bars):
        rows.append(
            {
                "date": bar.date.isoformat(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "sma20": sma20[i],
                "sma50": sma50[i],
                "rsi14": rsi14[i],
                "macd": macd_line[i],
                "macd_signal": macd_signal[i],
            }
        )
    return rows
