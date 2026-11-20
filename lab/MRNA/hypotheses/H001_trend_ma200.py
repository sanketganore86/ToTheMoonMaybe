HYPOTHESIS = {
    "ticker": "MRNA",
    "statement": "Holding MRNA only while Close > 200-day SMA beats buy-and-hold OOS on both Sharpe "
                 "and max drawdown, with timing better than chance.",
    "rationale": "Weekly candles: one giant bubble-and-crash (COVID vaccine boom, then -86%). In-sample "
                 "forward 20d return +11.1% above MA200 vs +0.7% below. Narrative-driven biotech "
                 "should trend.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True,
                      "beat_buy_hold_drawdown": True, "min_trades": 10},
}

def signal(df):
    c = df["Close"]
    return (c > c.rolling(200).mean()).astype(float)
