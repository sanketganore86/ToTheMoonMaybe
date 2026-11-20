import numpy as np
import pandas as pd

HYPOTHESIS = {
    "ticker": "AMD",
    "statement": "A 200-day trend filter with a +/-5% hysteresis band (enter above 1.05*SMA200, exit "
                 "below 0.95*SMA200) beats buy-and-hold OOS on Sharpe and drawdown with timing better "
                 "than chance.",
    "rationale": "H001's OOS candle chart showed losses came from whipsaw clusters at the MA. A band "
                 "ignores small crossings while still exiting multi-month busts like 2022.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True,
                      "beat_buy_hold_drawdown": True, "min_trades": 6},
}

def signal(df):
    c = df["Close"].to_numpy()
    ma = df["Close"].rolling(200).mean().to_numpy()
    pos, out = 0.0, np.zeros(len(c))
    for i in range(len(c)):
        if not np.isnan(ma[i]):
            if pos == 0 and c[i] > 1.05 * ma[i]:
                pos = 1.0
            elif pos == 1 and c[i] < 0.95 * ma[i]:
                pos = 0.0
        out[i] = pos
    return pd.Series(out, index=df.index)
