import numpy as np

HYPOTHESIS = {
    "ticker": "GOOGL",
    "statement": "Scaling GOOGL to a 25% annualised vol target (0.25 / realised 20d vol, cap 1) beats "
                 "buy-and-hold OOS on both Sharpe and max drawdown, with timing better than chance.",
    "rationale": "Unlike TSLA, GOOGL's highest-vol quintile does not have the highest next-day returns "
                 "(Q5 +0.10% vs Q3 +0.19%), so cutting exposure in vol spikes should remove risk more "
                 "than return. In-sample Sharpe 0.88 -> 0.99. Mechanism: Moreira-Muir vol-managed portfolios.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True,
                      "beat_buy_hold_drawdown": True, "min_trades": 10},
}

def signal(df):
    r = df["Close"].pct_change()
    return (0.25 / (r.rolling(20).std() * np.sqrt(252))).clip(upper=1.0)
