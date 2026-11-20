# Trade strategies and modeled options

Read this before writing a `T###` hypothesis.

## Template

```python
from pathlib import Path
import pandas as pd
from sentiment import features

HYPOTHESIS = {
    "ticker": "AXP",
    "statement": "After a cluster of insider open-market buys, a 30-day cash-secured put "
                 "(0.25 delta) on AXP reaches +1% of the account per trade more reliably "
                 "than the same put sold on random days.",
    "rationale": "Insider buying signals informed confidence; selling puts after it collects "
                 "premium while the downside is less likely.",
    "instrument": "cash_secured_put",
    "params": {"dte": 30, "short_delta": 0.25, "allocation": 1.0},
    "exit": {"take_profit": 0.01, "stop_loss": 0.04, "max_days": 25},
    "pass_criteria": {"max_p_value": 0.05, "min_trades": 20, "min_expectancy": 0.0,
                      "max_worst_trade": -0.10},
    # "start": "2018-03-01",
}

def entries(df: pd.DataFrame) -> pd.Series:
    """True at the close where the signal is known. The trade opens at the NEXT open."""
    f = features(Path(__file__).parents[1], df)
    return f["insider_buyers_90"] >= 2
```

## Sizing for capital protection
`protect.py` finds the safe size from the full history. As a rule of thumb from past runs,
single-stock trades with a −10% stop end up at about 5% of the account per position, once
overlapping positions are counted. Long options, which can lose 100%, end up at 1–2%.
Plan allocations near the safe size rather than discovering it after the test.

## Instruments and what "capital" means

The engine measures every return on capital tied up, then scales it by `allocation` to an
account-level return. Targets and stops are on the account.

| instrument | legs | capital (the 100% for a trade) | typical allocation |
|---|---|---|---|
| `stock_long` / `stock_short` | ±stock | entry price | 1.0 |
| `covered_call` | +stock −call(short_delta) | stock − call premium | 1.0 |
| `collar` | +stock −call(short_delta) +put(put_delta) | stock + put − call | 1.0 |
| `cash_secured_put` | −put(short_delta) | strike − premium (cash secured) | 1.0 |
| `put_credit_spread` | −put(short_delta) +put(width_pct lower) | width − credit (max loss) | 0.05–0.2 |
| `call_debit_spread` | +call(long_delta) −call(width_pct higher) | debit paid | 0.05–0.2 |
| `long_call` / `long_put` | +option(long_delta) | premium paid | 0.02–0.1 |

Levered structures need a small allocation. With allocation 1.0, a long call's 1% target
is pure noise: the bid-ask spread alone is about 10% round trip.

Parameters: `dte` (days to expiry, default 30), `short_delta` (0.30), `put_delta` (0.20),
`long_delta` (0.50), `width_pct` (0.05), `allocation` (1.0), and `spread_pct` (half-spread
as a fraction of premium, default 0.05; use 0.08–0.15 for thinly traded names such as AAOI or ASTS).

## Exits
`take_profit` (default 0.01), `stop_loss` (0.03) and `max_days` (20 sessions) are account
returns. Stocks fill at the target or stop intraday (High/Low), gaps fill at the open, and
the stop is assumed first when both are touched the same day. Options are marked at each
close and exit on target, stop, `max_days` or expiry. There is one position at a time.

## Pass criteria
- `min_expectancy` (default 0): the mean account return per trade OOS must exceed it.
- `max_worst_trade` (default −0.10): the worst OOS trade must lose less than this. This is
  the capital-protection check.
- `min_win_rate` (optional).
- `max_p_value`: the mean must beat the same exits on randomly timed entries.
- `min_trades` (default 20).

## The win-rate trap
A tight target with a wider stop wins often and loses big. Smoke test, AXP stock bought
every Monday with +1% target and −5% stop: an 83% win rate but −0.15% per trade. Always
judge on the mean and the worst trade. A stop near the target (e.g. +1% / −1%) halves the
win rate but bounds losses. Which is better is an empirical question; test each as its own
pre-registered hypothesis.

## How options are modeled (options.py)
- Black-Scholes, European exercise (early assignment ignored), no dividends.
- Rates come from ^IRX on the day.
- ATM implied vol: index = 0.91 × VIX; stock = 1.03 × blend(20-day, 252-day realized vol).
- Skew: iv(K) = iv_atm × (1 + 0.8·ln(S/K)), so OTM puts are richer and OTM calls cheaper.
- Costs per leg per side: max(5% of premium, $0.02) half-spread plus $0.65 per contract.
  Stock legs pay the stock cost.
- Validation (`validate_options.py`): replicating Cboe's real PUT index (monthly ATM SPX
  put-write), 2007–2026. The 0.91 factor was fitted on 2007–2016 (bias 0). On 2017–2026,
  which it was not fitted on, it overstates returns by +0.09%/month, with monthly
  correlation 0.98 and a matching worst month (−29% vs −28%). The single-stock vol premium
  is set below the index's measured 1.07, to stay conservative for option sellers.
- Weaknesses: there is no real per-stock implied vol (earnings run-ups and crush are
  missing), skew is a fixed shape, and liquidity is assumed. Treat option results as
  directional evidence. Validate anything promising with real chain data or paper trading.

## Evaluating someone else's trade alerts (bots, scanners, newsletters)
A screenshot of winning alerts cannot show skill. Before crediting any service:
1. **All alerts, not "selected" ones.** Losers and expired-worthless contracts must be in the log.
2. **A realistic exit rule.** "Peak bid" or "max gain" assumes selling at the exact high of the
   day. Check it: for a short-dated call, strike + peak price ≈ the underlying's day high.
   Use a fixed rule (time, target, close) instead.
3. **Many days, especially down days.** Alerts on one day are one bet on market direction, not
   N independent trades. Calls on high-beta names all win on an up-from-the-open day.
4. **A random baseline.** Compare against similar-delta, same-expiry calls on the same names
   at the same times. Leverage alone turns a 1–5% move into +100–500% on 0–1 DTE options.
5. **Sizing.** Every 0/1-DTE long option can lose 100%. Even a strong win rate needs tiny sizes.
Verify what you can with daily bars (`fetch_data.py`, open-to-high moves, close vs strike), and
ask for the full alert history before drawing conclusions.
