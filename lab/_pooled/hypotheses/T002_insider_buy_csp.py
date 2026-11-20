from sentiment import features

HYPOTHESIS = {
    "tickers": ["TSLA", "GOOGL", "AMD", "MRNA", "AXP", "V", "CAT", "AAOI", "ASTS"],
    "statement": "Selling a 30-day, 0.25-delta cash-secured put at the next open after a new insider "
                 "open-market purchase is filed earns a positive mean account return per trade (+1% target, "
                 "-5% stop, 25 sessions), better than the same put sold on random days. MODELED options.",
    "rationale": "Same signal as T001, expressed with premium selling: if insiders' confidence lowers "
                 "the odds of a sharp drop, short puts collect premium with fewer assignments. The random-"
                 "entry baseline captures the generic put-selling premium, so the signal must add to it.",
    "instrument": "cash_secured_put",
    "params": {"dte": 30, "short_delta": 0.25, "allocation": 1.0, "spread_pct": 0.08},
    "exit": {"take_profit": 0.01, "stop_loss": 0.05, "max_days": 25},
    "pass_criteria": {"max_p_value": 0.05, "min_trades": 20, "min_expectancy": 0.0, "max_worst_trade": -0.10},
}

def entries(df):
    f = features(None, df)
    b = f["insider_buy_90"]
    return (b > b.shift(1)).fillna(False)
