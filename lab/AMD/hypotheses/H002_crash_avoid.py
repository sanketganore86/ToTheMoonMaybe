HYPOTHESIS = {
    "ticker": "AMD",
    "statement": "Holding AMD except for the 5 sessions after a -2 sigma down day beats buy-and-hold "
                 "OOS Sharpe with timing better than chance.",
    "rationale": "In-sample, after big DOWN days AMD's next-day mean was -0.78% (t=-1.6) vs +0.11% "
                 "normally: crashes continue (forced selling, analyst downgrades follow).",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
}

def signal(df):
    r = df["Close"].pct_change()
    crash = r < -2 * r.rolling(60).std()
    recent_crash = crash.astype(float).rolling(5, min_periods=1).max()
    return 1.0 - recent_crash
