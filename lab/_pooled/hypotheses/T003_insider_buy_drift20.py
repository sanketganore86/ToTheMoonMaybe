from sentiment import features

HYPOTHESIS = {
    "tickers": ["TSLA", "GOOGL", "AMD", "MRNA", "AXP", "V", "CAT", "AAOI", "ASTS"],
    "statement": "Buying at the next open after a new insider open-market purchase is filed and holding "
                 "20 sessions (stop -10%, no profit target) earns a positive mean return per trade, better "
                 "than 20-session holds started on random days.",
    "rationale": "T001/T002 screened out, but their +1% target exited in 1-2 sessions while the documented "
                 "insider effect is a multi-week post-filing drift. This tests the mechanism directly.",
    "instrument": "stock_long",
    "exit": {"take_profit": 0.50, "stop_loss": 0.10, "max_days": 20},
    "pass_criteria": {"max_p_value": 0.05, "min_trades": 20, "min_expectancy": 0.0, "max_worst_trade": -0.12},
}

def entries(df):
    f = features(None, df)
    b = f["insider_buy_90"]
    return (b > b.shift(1)).fillna(False)
