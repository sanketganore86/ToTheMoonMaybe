from pathlib import Path
from sentiment import features

HYPOTHESIS = {
    "ticker": "AXP",
    "statement": "Holding AXP only while SPY is above its 200-day SMA beats buy-and-hold OOS Sharpe with "
                 "timing better than chance.",
    "rationale": "AXP is a credit-sensitive financial; the broad market regime beat buy&hold in both in-sample "
                 "halves (0.72 vs 0.48, 0.60 vs 0.43). Slower than the VIX fear filter (H003), so it should "
                 "not exit at short panic peaks. The failed H003 lowers the prior.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 6},
}

def signal(df):
    f = features(Path(__file__).parents[1], df)
    return (f["spy_trend"] > 0).astype(float)
