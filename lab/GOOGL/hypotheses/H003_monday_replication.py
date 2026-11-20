HYPOTHESIS = {
    "ticker": "GOOGL",
    "statement": "Replication of TSLA H003: holding GOOGL only on Mondays beats buy-and-hold OOS Sharpe "
                 "with timing better than chance.",
    "rationale": "TSLA showed a Monday effect (OOS p=0.057). A real weekend effect should replicate on "
                 "other stocks. GOOGL in-sample Monday was weak (t=+0.47), so prior is low.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    return (df.index.dayofweek == 4).astype(float)  # decided Friday close, held Monday

