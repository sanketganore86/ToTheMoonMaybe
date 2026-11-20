"""Pre-registered 2026-10-22, BEFORE any out-of-sample look. Agent-level hypothesis for paper agent "bold".

Context: on 2026-10-22 the market gapped down (semis led, VIX +9.7% at the open). In-sample (2005 -> 2020-04-03),
bold's rule (buy the 3 highest-sigma names at the open, +/-3% bracket, sell at the close) lost money in every
regime, and lost more when the previous close showed stress: VIX/VIX3M >= 0.95 or VIX >= 10% above its 20-day mean.
"""
HYPOTHESIS = {
    "id": "B001",
    "agent": "bold",
    "statement": "bold loses less per day if it stays in cash on days when, at the PREVIOUS close, VIX/VIX3M >= 0.95 "
                 "or VIX is >= 10% above its 20-day mean.",
    "rationale": "Backwardation / VIX spikes mean acute fear: intraday ranges widen, so +/-3% brackets on the most "
                 "volatile names hit the stop more often; opening spreads are also widest then. In-sample: -0.44% to "
                 "-0.69%/day in those regimes vs -0.26% otherwise.",
    "signal_known": "previous close (decided at 08:15 ET, no lookahead)",
    "pass_criteria": {
        "edge": "OOS mean daily return of filtered bold (cash = 0) minus unfiltered bold > 0, with permutation p < 0.05 "
                "(skip the same number of OOS days at random, 5000 draws)",
        "usable": "filtered bold OOS mean daily return > 0 AND worst day >= -2% AND max drawdown >= -10% "
                  "(capital-protection limits)",
    },
    "params": {"term_max": 0.95, "spike_max": 0.10},
    "split": 0.7,
    "start": "2006-07-17",  # VIX3M starts here
}


def skip(m):
    """m: DataFrame with term_prev and vix_spike_prev (both from the previous close). True = stay in cash."""
    p = HYPOTHESIS["params"]
    return (m["term_prev"] >= p["term_max"]) | (m["vix_spike_prev"] >= p["spike_max"])
