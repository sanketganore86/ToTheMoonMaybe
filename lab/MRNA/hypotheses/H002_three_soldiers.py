from patterns import three_white_soldiers

HYPOTHESIS = {
    "ticker": "MRNA",
    "statement": "Holding MRNA for 5 sessions after a three-white-soldiers candle pattern beats "
                 "buy-and-hold OOS Sharpe with timing better than chance.",
    "rationale": "In-sample: 5d forward return +3.98% after the pattern vs +1.35% baseline, 65% up "
                 "(n=124). Short-term momentum in a news-driven stock. The daily candle chart shows "
                 "runs of green candles into the May-2024 breakout.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    return three_white_soldiers(df).astype(float).rolling(5, min_periods=1).max()
