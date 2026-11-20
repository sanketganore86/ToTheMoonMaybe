from pathlib import Path
from sentiment import features

HYPOTHESIS = {
    "ticker": "ASTS",
    "statement": "Holding ASTS only when the VIX term structure is NOT complacent (VIX/VIX3M >= 0.85) beats "
                 "buy-and-hold OOS Sharpe with timing better than chance.",
    "rationale": "Speculative stocks lagged during market complacency in-sample: ASTS fwd-20d -4.84% when "
                 "VIX/VIX3M < 0.85 vs +8.76% on all days; the same held for AAOI (-0.98% vs +0.76%). Mechanism: complacent "
                 "markets precede risk-off rotations that hit high-beta speculative names hardest, while "
                 "fear periods precede sharp rebounds.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    f = features(Path(__file__).parents[1], df)
    return (f["term"] >= 0.85).astype(float)
