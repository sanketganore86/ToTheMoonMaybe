HYPOTHESIS = {
    "ticker": "AMD",
    "statement": "Replication of TSLA H003: holding AMD only on Mondays beats buy-and-hold OOS Sharpe "
                 "with timing better than chance.",
    "rationale": "Cross-asset check of the TSLA near-miss. AMD in-sample Monday +0.18% (t=+1.37).",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    return (df.index.dayofweek == 4).astype(float)  # decided Friday close, held Monday

