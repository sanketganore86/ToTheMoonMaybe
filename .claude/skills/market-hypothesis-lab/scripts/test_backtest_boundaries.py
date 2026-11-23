"""Regression tests for execution timing and train/holdout isolation."""
import unittest
from types import SimpleNamespace

import numpy as np
import pandas as pd

from backtest import position_returns
from trade_backtest import simulate


class BacktestBoundaries(unittest.TestCase):
    def test_close_signal_cannot_capture_gap_before_next_open(self):
        dates = pd.bdate_range("2024-01-01", periods=4)
        df = pd.DataFrame({"Open": [100, 150, 165, 170]}, index=dates)
        signal = pd.Series([1, 0, 0, 0], index=dates)
        ret, held, fees = position_returns(df, signal, 0.001)
        np.testing.assert_allclose(held * ret - fees, [0, 0.099, -0.001])
        self.assertEqual(ret.index[-1], dates[-2])

    def test_window_start_charges_for_first_position(self):
        dates = pd.bdate_range("2024-01-01", periods=4)
        df = pd.DataFrame({"Open": [100, 150, 165, 170]}, index=dates)
        signal = pd.Series(1, index=dates)
        _, held, fees = position_returns(df, signal, 0.001, dates[2])
        self.assertEqual(held.tolist(), [1])
        self.assertEqual(fees.tolist(), [0.001])

    def test_training_trades_do_not_use_holdout_exits(self):
        dates = pd.bdate_range("2024-01-01", periods=7)
        opening = np.full(len(dates), 100.0)
        market = SimpleNamespace(
            dates=dates, o=opening, h=opening.copy(), l=opening.copy(), c=opening.copy()
        )
        market.h[1] = 106
        market.h[4] = 106
        signal = np.array([True, False, True, True, False, False, False])
        exits = {"take_profit": 0.05, "stop_loss": 0.05, "max_days": 3}

        before = simulate(market, signal, 1, 4, "stock_long", {}, exits, 0)
        self.assertEqual(before.exit.tolist(), [dates[1]])
        holdout = simulate(market, signal, 4, len(dates), "stock_long", {}, exits, 0)
        self.assertEqual(holdout.exit.tolist(), [dates[4]])
        market.h[4] = 100
        market.l[4] = 90
        after = simulate(market, signal, 1, 4, "stock_long", {}, exits, 0)
        pd.testing.assert_frame_equal(before, after)


if __name__ == "__main__":
    unittest.main()
