HYPOTHESIS = {
    "ticker": "AMD",
    "statement": "Holding AMD only while Close > 200-day SMA beats buy-and-hold OOS on both Sharpe "
                 "and max drawdown, with timing better than chance.",
    "rationale": "Weekly candles show multi-year regimes (2006-2015 collapse of -96%, 2016+ boom). "
                 "In-sample forward 20d return +4.3% above MA200 vs -0.3% below. Also the cross-asset "
                 "check of TSLA H001, which failed on whipsaw.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True,
                      "beat_buy_hold_drawdown": True, "min_trades": 10},
}

def signal(df):
    c = df["Close"]
    return (c > c.rolling(200).mean()).astype(float)
