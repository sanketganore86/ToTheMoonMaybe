from patterns import inside_bar

HYPOTHESIS = {
    "ticker": "GOOGL",
    "statement": "Holding GOOGL for the session after an inside-bar candle (flat otherwise) earns a "
                 "higher OOS Sharpe than buy-and-hold with timing better than chance.",
    "rationale": "Only candlestick pattern with |t|>2 in-sample across GOOGL/AMD/MRNA (next-day +0.17%, "
                 "t=2.17, n=486). 1 hit in 30 pattern tests is what chance predicts, so this is "
                 "primarily a data-mining check. Mechanism: volatility compression before expansion.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    return inside_bar(df).astype(float)
