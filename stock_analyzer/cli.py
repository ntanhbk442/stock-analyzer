"""Command-line interface for stock-analyzer."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from typing import Dict, List, Optional, Sequence

from . import __version__
from .analysis import indicator_rows, summarize
from .data import VALID_INTERVALS, VALID_RANGES, DataError, load

SORT_KEYS = {
    "return": "total_return",
    "volatility": "volatility",
    "drawdown": "max_drawdown",
    "sharpe": "sharpe",
    "rsi": "rsi14",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stock-analyzer",
        description="Analyze stock prices from Yahoo Finance or local CSV files.",
        epilog="SOURCE is a ticker symbol (e.g. AAPL) or a path to a CSV file "
        "with Date/Open/High/Low/Close/Volume columns.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    def add_source_opts(p: argparse.ArgumentParser, default_range: str) -> None:
        p.add_argument("--range", "-r", dest="range_", default=default_range, choices=VALID_RANGES,
                       help=f"lookback period for ticker downloads (default: {default_range})")
        p.add_argument("--interval", "-i", default="1d", choices=VALID_INTERVALS,
                       help="bar size for ticker downloads (default: 1d)")

    p = sub.add_parser("analyze", help="summary statistics, indicators and signals for one stock")
    p.add_argument("source", metavar="SOURCE")
    add_source_opts(p, "1y")
    p.add_argument("--json", action="store_true", help="output JSON")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("history", help="print price bars, optionally with indicators")
    p.add_argument("source", metavar="SOURCE")
    add_source_opts(p, "3mo")
    p.add_argument("--limit", "-n", type=int, default=20, help="show only the last N bars (0 = all, default: 20)")
    p.add_argument("--indicators", action="store_true", help="add SMA20/SMA50/RSI14/MACD columns")
    p.add_argument("--format", "-f", choices=("table", "csv", "json"), default="table")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("compare", help="compare returns and risk across several stocks")
    p.add_argument("sources", metavar="SOURCE", nargs="+")
    add_source_opts(p, "1y")
    p.add_argument("--sort", "-s", choices=sorted(SORT_KEYS), default="return",
                   help="column to sort by, descending (default: return)")
    p.add_argument("--json", action="store_true", help="output JSON")
    p.set_defaults(func=cmd_compare)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except DataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


# ---------------------------------------------------------------- commands

def cmd_analyze(args: argparse.Namespace) -> int:
    history = load(args.source, range_=args.range_, interval=args.interval)
    s = summarize(history)
    if args.json:
        print(json.dumps(s, indent=2))
        return 0

    cur = f" {s['currency']}" if s["currency"] else ""
    print(f"{s['symbol']}  {_num(s['close'])}{cur}  {_signed(s['change'])} ({_pct(s['change_pct'])})")
    print(f"{s['start']} → {s['end']}  ({s['bars']} bars)")
    print()
    _print_section("Performance", [
        ("Total return", _pct(s["total_return"])),
        ("Annualized volatility", _pct(s["volatility"], signed=False)),
        ("Sharpe ratio", _num(s["sharpe"])),
        ("Max drawdown", _pct(s["max_drawdown"])),
        ("Period high / low", f"{_num(s['period_high'])} / {_num(s['period_low'])}"),
        ("Average volume", _int(s["avg_volume"])),
    ])
    _print_section("Indicators", [
        ("SMA 20 / 50 / 200", " / ".join(_num(s[k]) for k in ("sma20", "sma50", "sma200"))),
        ("EMA 12 / 26", f"{_num(s['ema12'])} / {_num(s['ema26'])}"),
        ("RSI 14", _num(s["rsi14"], 1)),
        ("MACD / signal / hist", " / ".join(_num(s[k], 3) for k in ("macd", "macd_signal", "macd_hist"))),
        ("Bollinger (20, 2σ)", " / ".join(_num(s[k]) for k in ("bb_lower", "bb_middle", "bb_upper"))),
    ])
    print("Signals")
    for line in s["signals"] or ["Not enough data for signals"]:
        print(f"  • {line}")
    print()
    print("Indicator readings are informational only, not investment advice.")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    history = load(args.source, range_=args.range_, interval=args.interval)
    rows = indicator_rows(history)
    if not args.indicators:
        keep = ("date", "open", "high", "low", "close", "volume")
        rows = [{k: r[k] for k in keep} for r in rows]
    if args.limit > 0:
        rows = rows[-args.limit:]

    if args.format == "json":
        print(json.dumps({"symbol": history.symbol, "currency": history.currency, "bars": rows}, indent=2))
    elif args.format == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: "" if v is None else v for k, v in r.items()})
    else:
        headers = list(rows[0].keys())
        table = [[_cell(k, r[k]) for k in headers] for r in rows]
        print(f"{history.symbol}" + (f" ({history.currency})" if history.currency else ""))
        _print_table([h.upper() for h in headers], table)
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    summaries: List[Dict] = []
    failures = 0
    for source in args.sources:
        try:
            summaries.append(summarize(load(source, range_=args.range_, interval=args.interval)))
        except DataError as exc:
            failures += 1
            print(f"warning: skipping {source}: {exc}", file=sys.stderr)
    if not summaries:
        raise DataError("no data could be loaded for any SOURCE")

    key = SORT_KEYS[args.sort]
    reverse = args.sort != "volatility"  # lower volatility ranks first
    summaries.sort(key=lambda s: (s[key] is None, -(s[key] or 0) if reverse else (s[key] or 0)))

    if args.json:
        fields = ("symbol", "close", "total_return", "volatility", "sharpe", "max_drawdown", "rsi14", "start", "end")
        print(json.dumps([{f: s[f] for f in fields} for s in summaries], indent=2))
    else:
        headers = ["SYMBOL", "CLOSE", "RETURN", "VOLATILITY", "SHARPE", "MAX DD", "RSI14", "TREND"]
        table = [
            [
                s["symbol"],
                _num(s["close"]),
                _pct(s["total_return"]),
                _pct(s["volatility"], signed=False),
                _num(s["sharpe"]),
                _pct(s["max_drawdown"]),
                _num(s["rsi14"], 1),
                _trend(s),
            ]
            for s in summaries
        ]
        _print_table(headers, table)
    return 1 if failures else 0


# ---------------------------------------------------------------- formatting

def _num(value: Optional[float], digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:,.{digits}f}"


def _signed(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:+,.2f}"


def _int(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:,.0f}"


def _pct(value: Optional[float], signed: bool = True) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:+.2f}%" if signed else f"{value * 100:.2f}%"


def _cell(key: str, value) -> str:
    if key == "date":
        return value
    if key == "volume":
        return _int(value)
    if key == "rsi14":
        return _num(value, 1)
    if key in ("macd", "macd_signal"):
        return _num(value, 3)
    return _num(value)


def _trend(s: Dict) -> str:
    sma50, sma200 = s.get("sma50"), s.get("sma200")
    if sma50 is None or sma200 is None:
        return "n/a"
    return "up" if sma50 > sma200 else "down"


def _print_section(title: str, items: List) -> None:
    print(title)
    width = max(len(label) for label, _ in items)
    for label, value in items:
        print(f"  {label:<{width}}  {value}")
    print()


def _print_table(headers: List[str], rows: List[List[str]]) -> None:
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]

    def fmt(cells: List[str]) -> str:
        # left-align the first column, right-align numbers
        return "  ".join(c.ljust(w) if i == 0 else c.rjust(w) for i, (c, w) in enumerate(zip(cells, widths)))

    print(fmt(headers))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(fmt(r))
