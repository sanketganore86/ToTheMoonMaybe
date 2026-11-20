from pathlib import Path
import numpy as np
import pandas as pd
from sentiment import features

HYPOTHESIS = {
    "ticker": "V",
    "statement": "News overreaction: going long V for one session after a >2-sigma overnight gap DOWN, "
                 "and short for one session after a >2-sigma gap UP or a high-attention (>2x volume) up day, "
                 "earns positive returns with timing better than chance OOS.",
    "rationale": "Sentiment shock mean-reverts: in-sample the rule averaged +0.30% per event (t=1.76, n=239); the "
                 "same sign held on AXP, V, CAT and AAOI. Mechanism: liquidity providers are paid to absorb "
                 "news-driven order imbalances. Satellite signal, so it is judged on timing, not vs buy&hold.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": False, "min_sharpe": 0.0, "min_trades": 20},
}

def signal(df):
    f = features(Path(__file__).parents[1], df)
    r = df["Close"].pct_change()
    gs = f["gap"].rolling(60).std()
    dn = f["gap"] < -2 * gs
    up = (f["gap"] > 2 * gs) | ((f["attention"] > np.log(2)) & (r > 0))
    s = pd.Series(0.0, index=df.index)
    s[up] = -1.0
    s[dn] = 1.0
    return s
