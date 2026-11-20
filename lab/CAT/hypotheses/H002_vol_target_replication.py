import numpy as np

HYPOTHESIS = {
    "ticker": "CAT",
    "statement": "Replication of GOOGL H005: scaling CAT to a 25% annualised vol target (0.25 / realised 20d "
                 "vol, cap 1) beats buy-and-hold OOS on both Sharpe and max drawdown, timing better than chance.",
    "rationale": "GOOGL H005 beat buy&hold on Sharpe and drawdown OOS (p=0.18). The mechanism predicts it "
                 "works where the highest-vol periods are not the best-return periods: in-sample CAT vol-Q5 "
                 "next-day +0.130% vs all-days +0.066%. Identical rule, no re-tuning.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "beat_buy_hold_drawdown": True, "min_trades": 10},
}

def signal(df):
    r = df["Close"].pct_change()
    return (0.25 / (r.rolling(20).std() * np.sqrt(252))).clip(upper=1.0)
