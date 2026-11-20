HYPOTHESIS = {
    "ticker": "TSLA",
    "statement": "Holding TSLA only on the trading day after Friday (Monday) earns a better OOS "
                 "Sharpe than buy-and-hold, with timing better than chance.",
    "rationale": "In-sample Monday mean return +0.61%/day (t=+3.5) vs +0.25% overall. Possible "
                 "mechanism: weekend news/announcements priced in Monday. Mechanism is weak, so "
                 "this doubles as a data-mining check.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    # decided at Friday's close, held through the next session
    return (df.index.dayofweek == 4).astype(float)
