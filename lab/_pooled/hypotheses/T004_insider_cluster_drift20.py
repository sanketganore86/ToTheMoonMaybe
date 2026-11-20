from sentiment import features

HYPOTHESIS = {
    "tickers": ["TSLA", "GOOGL", "AMD", "MRNA", "AXP", "V", "CAT", "AAOI", "ASTS"],
    "statement": "Buying at the next open when a second (or later) distinct insider purchase within 90 days "
                 "becomes public, holding 20 sessions (stop -10%), earns a positive mean return per trade, "
                 "better than random 20-session holds.",
    "rationale": "Cluster buying (several insiders independently) is the strongest form of the insider "
                 "signal in the literature and was the strongest in-sample row on AAOI (+24.6% fwd 20d).",
    "instrument": "stock_long",
    "exit": {"take_profit": 0.50, "stop_loss": 0.10, "max_days": 20},
    "pass_criteria": {"max_p_value": 0.05, "min_trades": 15, "min_expectancy": 0.0, "max_worst_trade": -0.12},
}

def entries(df):
    f = features(None, df)
    b, n = f["insider_buy_90"], f["insider_buyers_90"]
    return ((b > b.shift(1)) & (n >= 2)).fillna(False)
