"""Pre-registered 2026-10-22, BEFORE any out-of-sample look. Candidate design for "bold" v2.

In-sample (2005 -> 2020-04-03) bold v1's intraday rule lost in every regime. Lower-turnover families were then
explored in-sample: overnight holds and 1-day reversal earned less than costs; momentum rotation beat equal
weight weakly (6 variants scanned: hold 5/20 days x look-back 20/60/120 days; excess +0.07% to +0.44% per hold,
t <= 1.3). This variant was the most consistent across the in-sample halves. 6 variants explored -> treat any
pass with that in mind.
"""
HYPOTHESIS = {
    "id": "B002",
    "agent": "bold (v2 candidate)",
    "statement": "Every 20 sessions, at the open, holding the 3 names (of the live test's 10) with the highest "
                 "60-day return through the previous close beats holding all eligible names equally, after costs.",
    "rationale": "Cross-sectional momentum (winners keep outperforming for weeks; slow diffusion of news) with low "
                 "turnover, so opening costs are paid once per 20 days instead of daily.",
    "pass_criteria": {
        "edge": "OOS mean excess return per hold (top-3 minus equal-weight all) > 0, p < 0.05 vs 5000 random "
                "3-name picks from the same eligible names on the same dates",
        "usable": "capital protection at the planned size (100% invested): worst day >= -2% and max drawdown "
                  ">= -10% over the FULL history; otherwise report the safe size",
    },
    "params": {"hold": 20, "look": 60, "k": 3, "cost_per_hold": 0.002, "min_history": 252},
    "split": 0.7,
    "start": "2005-01-03",
}
