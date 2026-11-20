from pathlib import Path
from sentiment import features

HYPOTHESIS = {
    "ticker": "AAOI",
    "statement": "Contrarian: holding AAOI only during the 20 sessions after credit markets turn risk-off "
                 "(HYG/LQD more than 1% below its 50d mean) beats buy-and-hold OOS Sharpe, timing better than chance.",
    "rationale": "Opposite of the large-cap fear filter: in-sample AAOI Sharpe 0.47 holding after credit stress "
                 "vs 0.12 buy&hold (complement -0.25); fwd 20d +4.7% vs +0.8%. Mechanism: speculative small "
                 "caps get indiscriminately dumped in risk-off episodes and rebound hardest.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    f = features(Path(__file__).parents[1], df)
    return (f["credit"] < -0.01).astype(float).rolling(20, min_periods=1).max()
