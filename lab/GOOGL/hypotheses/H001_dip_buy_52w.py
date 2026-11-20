HYPOTHESIS = {
    "ticker": "GOOGL",
    "statement": "Holding GOOGL only while it is >10% below its 252-day high (dip-buying) earns a "
                 "higher OOS Sharpe than buy-and-hold, with timing better than chance.",
    "rationale": "In-sample GOOGL is a steady compounder (weekly candles: shallow pullbacks that "
                 "recover); forward 20d returns were HIGHER below MA200 (+2.0%) than above (+1.4%), "
                 "suggesting overreaction on dips in a quality name.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    c = df["Close"]
    return (c < 0.90 * c.rolling(252, min_periods=60).max()).astype(float)
