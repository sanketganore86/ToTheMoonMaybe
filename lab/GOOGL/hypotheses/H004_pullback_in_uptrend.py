HYPOTHESIS = {
    "ticker": "GOOGL",
    "statement": "Holding GOOGL for 10 sessions after it closes at a 10-day low WHILE above its "
                 "200-day SMA beats buy-and-hold OOS Sharpe with timing better than chance.",
    "rationale": "H001 failed by buying into a bear market. Restricting dip-buys to an established "
                 "uptrend keeps the overreaction mechanism but avoids falling knives.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    c = df["Close"]
    trigger = (c <= c.rolling(10).min()) & (c > c.rolling(200).mean())
    return trigger.astype(float).rolling(10, min_periods=1).max()
