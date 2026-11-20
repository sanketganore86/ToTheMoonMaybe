from pathlib import Path
from sentiment import features

HYPOTHESIS = {
    "ticker": "V",
    "statement": "Fear filter: holding V except during the 20 sessions after the VIX z-score exceeds +1 "
                 "beats buy-and-hold OOS Sharpe with timing better than chance.",
    "rationale": "In-sample, 'buying fear' hurt quality large caps; the complement helped: V Sharpe "
                 "0.91 when avoiding post-fear windows vs 0.84 buy&hold (AXP 0.81 vs 0.45, V 0.91 vs 0.84, CAT "
                 "0.54 vs 0.49). Mechanism: elevated market fear clusters (vol persistence) and large caps "
                 "with credit/cyclical exposure keep falling while it lasts. Same rule on AXP/V/CAT.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    f = features(Path(__file__).parents[1], df)
    fear = (f["vix_z"] > 1).astype(float).rolling(20, min_periods=1).max()
    return 1.0 - fear
