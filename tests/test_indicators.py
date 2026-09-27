import unittest

from stock_analyzer import indicators as ind


class IndicatorTests(unittest.TestCase):
    def test_sma(self):
        self.assertEqual(ind.sma([1, 2, 3, 4, 5], 3), [None, None, 2.0, 3.0, 4.0])

    def test_ema_seeded_with_sma(self):
        out = ind.ema([1, 2, 3, 4, 5], 3)
        self.assertEqual(out[:2], [None, None])
        self.assertAlmostEqual(out[2], 2.0)
        self.assertAlmostEqual(out[3], 3.0)  # 4*0.5 + 2*0.5
        self.assertAlmostEqual(out[4], 4.0)

    def test_ema_skips_leading_none(self):
        out = ind.ema([None, None, 2.0, 4.0, 6.0], 2)
        self.assertEqual(out[:3], [None, None, None])
        self.assertAlmostEqual(out[3], 3.0)
        self.assertAlmostEqual(out[4], 6.0 * (2 / 3) + 3.0 * (1 / 3))

    def test_rsi_extremes(self):
        self.assertEqual(ind.last(ind.rsi(list(range(1, 30)), 14)), 100.0)
        self.assertEqual(ind.last(ind.rsi(list(range(30, 1, -1)), 14)), 0.0)
        self.assertEqual(ind.last(ind.rsi([5.0] * 20, 14)), 50.0)

    def test_rsi_known_value(self):
        # Alternating +1/-1 moves give equal average gain and loss.
        values = [10 + (i % 2) for i in range(40)]
        self.assertAlmostEqual(ind.last(ind.rsi(values, 14)), 50.0, delta=5)

    def test_macd_lengths_and_sign(self):
        values = [float(i) for i in range(1, 60)]
        line, signal, hist = ind.macd(values)
        self.assertEqual(len(line), len(values))
        self.assertIsNone(line[24])
        self.assertIsNotNone(line[25])
        self.assertIsNotNone(signal[33])
        self.assertGreater(line[-1], 0)

    def test_bollinger_constant_series(self):
        lower, mid, upper = ind.bollinger([10.0] * 25, 20)
        self.assertEqual((lower[-1], mid[-1], upper[-1]), (10.0, 10.0, 10.0))
        self.assertIsNone(mid[18])

    def test_returns_and_drawdown(self):
        values = [100, 120, 90, 110]
        self.assertAlmostEqual(ind.total_return(values), 0.10)
        self.assertAlmostEqual(ind.max_drawdown(values), -0.25)
        self.assertIsNone(ind.total_return([100]))

    def test_volatility_and_sharpe(self):
        self.assertAlmostEqual(ind.annualized_volatility([100, 101, 102.01, 103.0301]), 0.0, places=9)
        self.assertIsNone(ind.sharpe_ratio([100, 100, 100]))
        self.assertGreater(ind.annualized_volatility([100, 110, 95, 105]), 0)


if __name__ == "__main__":
    unittest.main()
