import pandas as pd

HYPOTHESIS = {
    "ticker": "TSLA",
    "statement": "Holding TSLA only while Close > 200-day SMA (flat otherwise) gives a higher "
                 "OOS Sharpe than buy-and-hold, with timing better than chance.",
    "rationale": "In-sample, forward 20d returns averaged +6.1% above MA200 vs +4.2% below; "
                 "trend persistence from herding/slow information diffusion.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    c = df["Close"]
    return (c > c.rolling(200).mean()).astype(float)
