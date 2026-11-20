from sentiment import features

HYPOTHESIS = {
    "tickers": ["TSLA", "GOOGL", "AMD", "MRNA", "AXP", "V", "CAT", "AAOI", "ASTS"],
    "statement": "Buying the stock at the next open after a new insider open-market purchase is filed "
                 "(SEC Form 4, code P) earns a positive mean account return per trade with a +1% target, "
                 "-5% stop and 20-session limit, better than the same trade on random days.",
    "rationale": "Insiders buying with their own cash is the best-documented sentiment signal in the "
                 "academic literature (post-filing drift over weeks). In-sample on AAOI the 20-day forward "
                 "return was +4.2% after insider buys vs +0.8% overall. Rare per stock, so pooled across "
                 "all 9 with one identical rule.",
    "instrument": "stock_long",
    "exit": {"take_profit": 0.01, "stop_loss": 0.05, "max_days": 20},
    "pass_criteria": {"max_p_value": 0.05, "min_trades": 20, "min_expectancy": 0.0, "max_worst_trade": -0.10},
}

def entries(df):
    f = features(None, df)  # lab comes from df.attrs (set by the engine)
    b = f["insider_buy_90"]
    return (b > b.shift(1)).fillna(False)  # a new purchase became public today
