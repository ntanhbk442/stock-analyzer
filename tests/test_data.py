import os
import tempfile
import unittest

from stock_analyzer.data import DataError, load, load_csv, parse_yahoo_chart

DATA = os.path.join(os.path.dirname(__file__), "data")


class CsvTests(unittest.TestCase):
    def test_load_csv(self):
        h = load(os.path.join(DATA, "uptrend.csv"))
        self.assertEqual(h.symbol, "UPTREND")
        self.assertEqual(len(h.bars), 260)
        self.assertLess(h.bars[0].date, h.bars[-1].date)

    def test_missing_file(self):
        with self.assertRaises(DataError):
            load_csv("does-not-exist.csv")

    def test_missing_close_column(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("Date,Open\n2024-01-02,1\n")
        try:
            with self.assertRaisesRegex(DataError, "close"):
                load_csv(fh.name)
        finally:
            os.unlink(fh.name)

    def test_skips_null_rows_and_sorts(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("Date,Close\n2024-01-03,11\n2024-01-02,10\n2024-01-04,null\n")
        try:
            h = load_csv(fh.name)
            self.assertEqual(h.closes, [10.0, 11.0])
        finally:
            os.unlink(fh.name)


class YahooParseTests(unittest.TestCase):
    def test_parse_chart(self):
        payload = {
            "chart": {
                "result": [{
                    "meta": {"symbol": "AAPL", "currency": "USD"},
                    "timestamp": [1704205800, 1704292200, 1704378600],
                    "indicators": {"quote": [{
                        "open": [1.0, 2.0, None],
                        "high": [1.5, 2.5, None],
                        "low": [0.5, 1.5, None],
                        "close": [1.2, 2.2, None],
                        "volume": [100, 200, None],
                    }]},
                }],
                "error": None,
            }
        }
        h = parse_yahoo_chart("aapl", payload)
        self.assertEqual(h.symbol, "AAPL")
        self.assertEqual(h.currency, "USD")
        self.assertEqual(h.closes, [1.2, 2.2])

    def test_parse_error(self):
        payload = {"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}}
        with self.assertRaisesRegex(DataError, "No data found"):
            parse_yahoo_chart("XXXX", payload)


if __name__ == "__main__":
    unittest.main()
