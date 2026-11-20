from pathlib import Path
import numpy as np
import pandas as pd

HYPOTHESIS = {
    "ticker": "AMD",
    "statement": "Holding AMD only while the semiconductor ETF SMH is in an uptrend (enter SMH > "
                 "1.03*SMA200, exit SMH < 0.97*SMA200) beats buy-and-hold OOS on Sharpe and drawdown "
                 "with timing better than chance.",
    "rationale": "AMD is a high-beta semis name; the sector cycle drives it. In-sample AMD next-day "
                 "+0.18% (t=2.9) when SMH > MA200 vs -0.10% below. The smoother sector ETF plus a 3% "
                 "band should avoid the own-price whipsaw seen in H001.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True,
                      "beat_buy_hold_drawdown": True, "min_trades": 6},
}

_SMH = pd.read_csv(Path(__file__).parents[1] / "data" / "SMH.csv", index_col=0, parse_dates=True)["Close"]

def signal(df):
    s = _SMH.reindex(df.index).ffill()          # only dates up to df's last row are used
    c, ma = s.to_numpy(), s.rolling(200).mean().to_numpy()
    pos, out = 0.0, np.zeros(len(c))
    for i in range(len(c)):
        if not np.isnan(ma[i]):
            if pos == 0 and c[i] > 1.03 * ma[i]:
                pos = 1.0
            elif pos == 1 and c[i] < 0.97 * ma[i]:
                pos = 0.0
        out[i] = pos
    return pd.Series(out, index=df.index)
