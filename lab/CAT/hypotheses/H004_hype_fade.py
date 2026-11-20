from pathlib import Path
import numpy as np
from sentiment import features

HYPOTHESIS = {
    "ticker": "CAT",
    "statement": "Hype-fade: holding CAT except for the 5 sessions after a high-attention up day (volume > 2x "
                 "50d median and close up) beats buy-and-hold OOS Sharpe with timing better than chance.",
    "rationale": "The only sentiment rule that beat buy&hold in BOTH in-sample halves on AXP, V and CAT "
                 "(CAT: 0.39 vs 0.35 / 0.70 vs 0.67). Mechanism: attention-driven buying is followed by giveback as the "
                 "marginal buyer is exhausted. Caveat: overlaps with the short leg of H001 (news overreaction), "
                 "which failed OOS, so the prior is lowered.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    f = features(Path(__file__).parents[1], df)
    r = df["Close"].pct_change()
    hype = ((f["attention"] > np.log(2)) & (r > 0)).astype(float)
    return 1.0 - hype.rolling(5, min_periods=1).max()
