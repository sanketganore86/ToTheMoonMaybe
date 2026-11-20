"""Pre-registered 2026-11-05 together with D001. NOT independent of what was seen: see JOURNAL.md."""
HYPOTHESIS = {
    "id": "D002",
    "statement": "D001 restricted to uptrends: when SPY closed above its 200-day average the day before the sell-off, "
                 "buying large caps at the sell-off close and selling 5 sessions later beats random uptrend days "
                 "(pooled mean > random mean, and > 0).",
    "rationale": "Earlier lab finding: dip-buying without a trend condition buys all the way through bear markets. "
                 "In an uptrend a sharp drop is more often a shake-out than the start of a bear market.",
    "rule": "event = SPY close-to-close <= -2% AND SPY close > its 200-day average on the previous day; random days are "
            "drawn only from days with SPY above its 200-day average (so the test is the dip, not the trend)",
    "pass_criteria": {"min_mean": 0.0, "max_p_value": 0.05, "min_event_days": 10,
                      "screen": "mean > 0 and beats random uptrend days in both in-sample halves"},
    "planned_size": "20% of the account per event day, split equally across the stocks (up to 5 overlapping baskets = 100%)",
}


def select(spy):
    return (spy.ret <= -0.02) & (spy.above200 == True)


def random_pool(spy):
    return spy.index[spy.above200 == True]
