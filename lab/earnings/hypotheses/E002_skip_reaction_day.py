"""Pre-registered 2026-10-28, after in-sample exploration only (explore.py; events before the 70% split)."""
HYPOTHESIS = {
    "id": "E002",
    "statement": "For a long open-to-close trade, a stock's earnings reaction day is WORSE than its ordinary days: "
                 "mean net return on reaction days minus ordinary days < 0. If supported, agents that buy at the "
                 "open should skip a stock on its reaction day (a capital-protection rule, not a profit rule).",
    "rationale": "The report is already in the opening price, the opening spread is widest on that day and the "
                 "intraday range is largest. In-sample: -0.258%/trade on reaction days vs -0.147% on ordinary days.",
    "rule": "difference of means, reaction days vs ordinary days of the same tickers and period; "
            "p = share of 5000 random draws of ordinary days (same count per ticker) whose mean is <= the reaction-day mean",
    "pass_criteria": {"max_diff": 0.0, "max_p_value": 0.05, "screen": "difference < 0 in both in-sample halves"},
}
def select(ev):
    return ev
