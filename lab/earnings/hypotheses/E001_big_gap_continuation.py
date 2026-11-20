"""Pre-registered 2026-10-28, after in-sample exploration only (explore.py; events before the 70% split)."""
HYPOTHESIS = {
    "id": "E001",
    "statement": "On an earnings reaction day, buying at the open when the stock gapped up >= 5% and selling at the "
                 "close earns more than costs (mean net return per trade > 0) and more than ordinary days.",
    "rationale": "Post-earnings drift: big positive surprises keep being priced in during the first session. "
                 "In-sample: gap > +5% was the only bucket above zero (+0.19%/trade, t = 0.85, n = 310).",
    "rule": "gap >= 0.05; buy at the open, sell at the close (no bracket); bold's daily-bar costs",
    "pass_criteria": {"min_mean": 0.0, "max_p_value": 0.05, "min_trades": 30, "screen": "mean > 0 in both in-sample halves"},
}
def select(ev):
    return ev[ev.gap >= 0.05]
