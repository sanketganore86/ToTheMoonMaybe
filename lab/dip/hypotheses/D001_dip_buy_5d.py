"""Pre-registered 2026-11-05, before any test in this lab (see JOURNAL.md for what had already been seen)."""
HYPOTHESIS = {
    "id": "D001",
    "statement": "Buying large caps at the close of a day when SPY fell >= 2% and selling 5 sessions later earns more "
                 "per trade than buying on random days: pooled mean net return > random-day mean, and > 0.",
    "rationale": "Short-term reversal: forced selling and liquidity demand on sell-off days push prices below value "
                 "for a few days (hypothesis_ideas.md, 'buy after a large down day, hold 1-5 days').",
    "rule": "event = SPY close-to-close <= -2%; buy all 30 tickers at the event close, sell at the close 5 sessions later; "
            "p = share of 5000 draws of the same number of random trading days (same period, all 30 tickers) whose "
            "pooled mean is >= the event mean",
    "pass_criteria": {"min_mean": 0.0, "max_p_value": 0.05, "min_event_days": 10,
                      "screen": "mean > 0 and beats random days in both in-sample halves"},
    "planned_size": "20% of the account per event day, split equally across the stocks (up to 5 overlapping baskets = 100%)",
}


def select(spy):
    return spy.ret <= -0.02


def random_pool(spy):
    return spy.index
