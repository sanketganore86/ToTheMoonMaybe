import numpy as np
import pandas as pd

HYPOTHESIS = {
    "ticker": "MRNA",
    "statement": "A 50-day trend filter with a +/-5% band (enter above 1.05*SMA50, exit below "
                 "0.95*SMA50) beats buy-and-hold OOS on Sharpe and drawdown with timing better than "
                 "chance, with at least 10 position changes.",
    "rationale": "H001 looked spectacular but traded once. MRNA trends strongly (in-sample MA50: +8.3% "
                 "fwd 20d above vs +1.9% below); a faster rule trades enough to be testable, and the "
                 "band limits whipsaw seen on TSLA/AMD.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True,
                      "beat_buy_hold_drawdown": True, "min_trades": 10},
}

def signal(df):
    c = df["Close"].to_numpy()
    ma = df["Close"].rolling(50).mean().to_numpy()
    pos, out = 0.0, np.zeros(len(c))
    for i in range(len(c)):
        if not np.isnan(ma[i]):
            if pos == 0 and c[i] > 1.05 * ma[i]:
                pos = 1.0
            elif pos == 1 and c[i] < 0.95 * ma[i]:
                pos = 0.0
        out[i] = pos
    return pd.Series(out, index=df.index)
