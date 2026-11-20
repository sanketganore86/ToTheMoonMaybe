import numpy as np

HYPOTHESIS = {
    "ticker": "TSLA",
    "statement": "Scaling the TSLA position to target 40% annualised volatility (position = 0.40 / "
                 "realised 20d vol, capped at 1, long-only) beats buy-and-hold on both OOS Sharpe "
                 "and OOS max drawdown.",
    "rationale": "Volatility clusters strongly (|r| lag-1 autocorr +0.17) while direction does not "
                 "(r autocorr ~0), so de-risking after vol spikes should cut drawdowns more than returns.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True,
                      "beat_buy_hold_drawdown": True, "min_trades": 10},
}

def signal(df):
    r = df["Close"].pct_change()
    vol = r.rolling(20).std() * np.sqrt(252)
    return (0.40 / vol).clip(upper=1.0)
