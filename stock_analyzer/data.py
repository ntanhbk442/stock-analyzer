"""Price data loading: Yahoo Finance chart API or local CSV files."""

from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import List, Optional

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
VALID_RANGES = ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
VALID_INTERVALS = ("1d", "1wk", "1mo")


class DataError(Exception):
    """Raised when price data cannot be loaded."""


@dataclass
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class PriceHistory:
    symbol: str
    bars: List[Bar]
    currency: Optional[str] = None
    source: str = ""

    @property
    def closes(self) -> List[float]:
        return [b.close for b in self.bars]


def is_csv_source(source: str) -> bool:
    return source.lower().endswith(".csv") or os.path.isfile(source)


def load(source: str, range_: str = "1y", interval: str = "1d") -> PriceHistory:
    """Load history from a CSV path or, otherwise, treat `source` as a ticker."""
    if is_csv_source(source):
        return load_csv(source)
    return fetch_yahoo(source, range_=range_, interval=interval)


def _parse_float(value: str) -> Optional[float]:
    value = (value or "").strip().replace(",", "")
    if value in ("", "null", "NaN", "nan", "-"):
        return None
    return float(value)


def _parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        raise DataError(f"Unrecognized date: {value!r}") from None


def load_csv(path: str) -> PriceHistory:
    """Read a CSV with Date/Open/High/Low/Close/Volume columns (Yahoo export format)."""
    if not os.path.isfile(path):
        raise DataError(f"CSV file not found: {path}")
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise DataError(f"CSV file is empty: {path}")
        cols = {name.strip().lower(): name for name in reader.fieldnames}
        missing = [c for c in ("date", "close") if c not in cols]
        if missing:
            raise DataError(f"CSV {path} is missing column(s): {', '.join(missing)}")

        def get(row, key):
            name = cols.get(key)
            return row.get(name, "") if name else ""

        bars = []
        for row in reader:
            close = _parse_float(get(row, "close"))
            if close is None:
                continue
            open_ = _parse_float(get(row, "open"))
            high = _parse_float(get(row, "high"))
            low = _parse_float(get(row, "low"))
            volume = _parse_float(get(row, "volume"))
            bars.append(
                Bar(
                    date=_parse_date(get(row, "date")),
                    open=open_ if open_ is not None else close,
                    high=high if high is not None else close,
                    low=low if low is not None else close,
                    close=close,
                    volume=int(volume or 0),
                )
            )
    if not bars:
        raise DataError(f"No price rows found in {path}")
    bars.sort(key=lambda b: b.date)
    symbol = os.path.splitext(os.path.basename(path))[0].upper()
    return PriceHistory(symbol=symbol, bars=bars, source=path)


def fetch_yahoo(symbol: str, range_: str = "1y", interval: str = "1d", timeout: float = 15.0) -> PriceHistory:
    """Download daily/weekly/monthly bars from Yahoo Finance's public chart endpoint."""
    if range_ not in VALID_RANGES:
        raise DataError(f"Invalid range {range_!r}; choose from {', '.join(VALID_RANGES)}")
    if interval not in VALID_INTERVALS:
        raise DataError(f"Invalid interval {interval!r}; choose from {', '.join(VALID_INTERVALS)}")
    symbol = symbol.strip().upper()
    query = urllib.parse.urlencode({"range": range_, "interval": interval, "events": "div,splits"})
    url = YAHOO_CHART_URL.format(symbol=urllib.parse.quote(symbol)) + "?" + query
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (stock-analyzer CLI)"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise DataError(f"Unknown symbol: {symbol}") from None
        raise DataError(f"Yahoo Finance request failed for {symbol}: HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DataError(f"Could not reach Yahoo Finance for {symbol}: {exc}") from None
    return parse_yahoo_chart(symbol, payload)


def parse_yahoo_chart(symbol: str, payload: dict) -> PriceHistory:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        desc = chart["error"].get("description") or chart["error"]
        raise DataError(f"Yahoo Finance error for {symbol}: {desc}")
    results = chart.get("result") or []
    if not results:
        raise DataError(f"No data returned for {symbol}")
    result = results[0]
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    meta = result.get("meta") or {}

    bars = []
    for i, ts in enumerate(timestamps):
        def at(key):
            values = quote.get(key) or []
            return values[i] if i < len(values) else None

        close = at("close")
        if close is None:
            continue
        bars.append(
            Bar(
                date=datetime.fromtimestamp(ts, tz=timezone.utc).date(),
                open=at("open") if at("open") is not None else close,
                high=at("high") if at("high") is not None else close,
                low=at("low") if at("low") is not None else close,
                close=close,
                volume=int(at("volume") or 0),
            )
        )
    if not bars:
        raise DataError(f"No price data returned for {symbol}")
    return PriceHistory(
        symbol=meta.get("symbol", symbol),
        bars=bars,
        currency=meta.get("currency"),
        source="yahoo",
    )
