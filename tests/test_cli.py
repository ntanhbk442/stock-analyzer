import contextlib
import io
import json
import os
import unittest

from stock_analyzer.cli import main

DATA = os.path.join(os.path.dirname(__file__), "data")
UP = os.path.join(DATA, "uptrend.csv")
DOWN = os.path.join(DATA, "downtrend.csv")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def test_analyze_text(self):
        code, out, _ = run("analyze", UP)
        self.assertEqual(code, 0)
        self.assertIn("UPTREND", out)
        self.assertIn("RSI 14", out)
        self.assertIn("Bullish trend", out)

    def test_analyze_json(self):
        code, out, _ = run("analyze", DOWN, "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["bars"], 260)
        self.assertLess(data["total_return"], 0)
        self.assertIsNotNone(data["sma200"])

    def test_history_limit_and_formats(self):
        code, out, _ = run("history", UP, "-n", "5", "--format", "csv")
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual(lines[0], "date,open,high,low,close,volume")
        self.assertEqual(len(lines), 6)

        code, out, _ = run("history", UP, "-n", "3", "--indicators", "--format", "json")
        bars = json.loads(out)["bars"]
        self.assertEqual(len(bars), 3)
        self.assertIn("rsi14", bars[0])

        code, out, _ = run("history", UP, "-n", "3")
        self.assertIn("CLOSE", out)

    def test_compare_sorted(self):
        code, out, _ = run("compare", DOWN, UP, "--json")
        self.assertEqual(code, 0)
        self.assertEqual([r["symbol"] for r in json.loads(out)], ["UPTREND", "DOWNTREND"])

        code, out, _ = run("compare", UP, DOWN, "--sort", "volatility", "--json")
        self.assertEqual(json.loads(out)[0]["symbol"], "UPTREND")

    def test_compare_partial_failure(self):
        code, out, err = run("compare", UP, "missing.csv")
        self.assertEqual(code, 1)
        self.assertIn("UPTREND", out)
        self.assertIn("skipping missing.csv", err)

    def test_negative_limit_rejected(self):
        with self.assertRaises(SystemExit) as ctx, contextlib.redirect_stderr(io.StringIO()):
            main(["history", UP, "-n", "-5"])
        self.assertEqual(ctx.exception.code, 2)

    def test_bad_source(self):
        code, _, err = run("analyze", "missing.csv")
        self.assertEqual(code, 1)
        self.assertIn("error:", err)


if __name__ == "__main__":
    unittest.main()
