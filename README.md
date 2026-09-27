# stock-analyzer

A command-line tool that analyzes stock prices. It has no third-party dependencies and needs only Python 3.9+.

Data comes from Yahoo Finance's public chart API when you pass a ticker, or from a local CSV file when you pass a path.

## Install

```bash
pip install -e .          # installs the `stock-analyzer` command
# or run without installing:
python -m stock_analyzer --help
```

## Usage

```bash
# Summary: performance, risk, indicators and plain-language signals
stock-analyzer analyze AAPL
stock-analyzer analyze MSFT --range 2y --json

# Price bars (last 20 by default), optionally with indicators
stock-analyzer history TSLA --range 6mo -n 10 --indicators
stock-analyzer history NVDA --range 1y -n 0 --format csv > nvda.csv

# Side-by-side comparison, sorted by return / volatility / drawdown / sharpe / rsi
stock-analyzer compare AAPL MSFT GOOGL AMZN --sort sharpe

# Local CSV files work anywhere a ticker does
stock-analyzer analyze tests/data/uptrend.csv
```

Options shared by every command:

| Option | Values | Default |
| --- | --- | --- |
| `--range`, `-r` | `1d 5d 1mo 3mo 6mo 1y 2y 5y 10y ytd max` | `1y` (`3mo` for `history`) |
| `--interval`, `-i` | `1d 1wk 1mo` | `1d` |

A CSV file must have `Date` and `Close` columns. `Open`, `High`, `Low` and `Volume` are optional. The header format matches Yahoo Finance's CSV export.

## What it computes

- **Performance:** total return, annualized volatility, Sharpe ratio (risk-free rate of 0), max drawdown, period high and low, average volume.
- **Indicators:** SMA 20/50/200, EMA 12/26, RSI 14 (Wilder), MACD 12/26/9, Bollinger Bands (20, 2σ).
- **Signals:** trend regime from the 50- vs 200-day SMA, price vs. moving averages, RSI overbought/oversold, MACD momentum, Bollinger breakouts.

Volatility and Sharpe are annualized assuming 252 trading periods per year, so they are only meaningful with daily bars (`--interval 1d`).

Signals are informational only and are not investment advice.

## Development

```bash
python -m unittest discover -s tests -v
```

The test suite uses the synthetic CSV fixtures in `tests/data/` and never touches the network.

## Layout

```
stock_analyzer/
  cli.py         argparse commands and output formatting
  data.py        Yahoo Finance and CSV loaders
  indicators.py  pure-Python indicator math
  analysis.py    summary and signal generation
tests/           unit tests and CSV fixtures
```
