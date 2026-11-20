# Lab: bold (paper agent "bold": top-3 sigma names, bought at the open, +/-3% bracket, sell at the close)

Daily-bar simulation of bold's rule (`bold_sim.py`): entry at the open with the paper engine's opening costs
(0.135%), stop assumed first if a day touches both +3% and -3% (2% of trades), exits at the close 0.045%.
Universe = the live test's 10 names (MRNA from 2018), each eligible after 252 days of history.

## 2026-10-22 — what triggered the sell-off (observation, no test)
- Wed 10-21 was calm and risk-on (VIX -3.6%, SMH +1.9%): no pre-open sentiment gauge flagged anything.
- The move came overnight: at Thursday's open SMH -3.6%, QQQ -1.6%, SPY -0.9%, VIX +9.7%; it deepened through
  the day (SMH -6.0%, VIX +14% at the close). IWM finished flat; staples/utilities/health rose (XLP +3.3%,
  XLU +2.0%, XLV +1.3%): a rotation out of tech/semis, not a broad crash.
- The news behind it is NOT verified: the GDELT headline search was refused (polite.py cooldown after
  repeated failures), so no cause is recorded. Retry later; don't guess.
- MRNA was separate: -6% at 12:30, -25.9% by 14:00 (low 14:01), closed -17.6%. AMD gapped -5.3% at the open.

## In-sample exploration (2005 -> 2020-04-03; OOS hidden)
- bold's rule loses in every regime: -0.34%/day (stop-first) and still -0.22% per trade if every double-touch
  is assumed to hit the target first. High-sigma names drift ~0% open->close (-0.015%); costs are ~0.2% per trade.
- It loses more after stressed closes: VIX/VIX3M >= 1: -0.69%/day; VIX >= 25% above its 20d mean: -0.60%/day;
  vs -0.26% in calm regimes. SPY's opening gap and VIX's opening jump did not separate good from bad days.
- "Profit" ideas from today did not generalize: defensives (KO, NEE, XOM, PLD) bought at the open on SPY gap-down
  days returned -0.19% open->close (t=-3.2; worse than on other days); fading a stock's own big gap: no edge
  after costs (best +0.30% before 0.18% costs, t=1.3).

## B001 riskoff_skip — REJECTED (edge) / NOT USABLE — tested 2026-10-22
Pre-registered: `hypotheses/B001_riskoff_skip.py`. bold stays in cash when the previous close shows
VIX/VIX3M >= 0.95 or VIX >= 10% above its 20-day mean.
- Screen (in-sample halves): passed both (2006-13 diff +0.25%/day p=0.0002; 2013-20 diff +0.12%/day p=0.001).
- OOS 2020-09-17 -> 2026-10-22 (1,530 days, 392 skipped): bold -0.31%/day -> filtered -0.21%/day,
  diff +0.10%/day, permutation p = 0.14 (needed < 0.05): **REJECTED**.
- Capital protection: filtered bold still loses: worst day -3.2%, max drawdown -97% (unfiltered -99%): **NOT USABLE**.
- Interpretation: the risk-off skip helped in 2006-2020 (2008 and 2011 dominate the stressed days) but
  much less after 2020, when stress days were rarer and bold also lost on calm days. The filter treats a
  symptom; the cause is that bold's rule has no edge: zero intraday drift on the most volatile names,
  costs of ~0.2% per trade, and a symmetric bracket. Live days 1-4 (mean +0.06%/day) are consistent with
  the simulation's -0.3%/day given a 1.5% daily standard deviation (4 days is noise).
- Rules out: sentiment filters as a fix for bold. Points to: a different rule (fewer, cheaper entries;
  not at the open), or retiring bold after the test.

## bold v2 search (2026-10-22) — in-sample exploration, 2005 -> 2020-04-03
Lower-turnover families, net of the paper engine's costs:
- Overnight hold (buy 15:55, sell next open): +0.05%/night all names, +0.11% top-3 sigma; costs ~0.18%. Dead.
- 1-day reversal (buy today's worst name at the close): +0.06% to sell next open, +0.09% next close; below costs. Dead.
- Momentum rotation: a first pass looked strong (+2%/20 days) but used the same day's close to rank and buy at that
  day's open (lookahead) and compared with zero instead of the market. Fixed: top-3 vs equal-weight all names,
  6 variants (hold 5/20 x look-back 20/60/120): excess +0.07% to +0.44% per hold, t <= 1.3.

## B002 momentum_rotation — REJECTED (edge) / NOT USABLE at 100% — tested 2026-10-22
Pre-registered: `hypotheses/B002_momentum_rotation.py` (hold 20 sessions, top 3 of 10 by 60-day return through
the previous close, bought at the open; benchmark = all eligible names equally; 6 variants explored in-sample).
- Screen: beat equal weight in both halves (+0.17% p=0.36; +0.37% p=0.19), not significantly.
- OOS 2020-04-06 -> 2026-09-17 (82 holds): top-3 +3.42% vs all +2.47% per hold, excess +0.95%, p = 0.07
  (needed < 0.05): **REJECTED**.
- Capital protection (full history, 100% invested): worst day -13.1%, max drawdown -66%: **NOT USABLE**.
  Safe size 10% of the account -> about +4.5%/year from that sleeve OOS, roughly T-bill territory.
- Interpretation: a near-miss driven by 2020-2024 trends in AMD/MRNA (look at `oos_picks`); the edge is small
  relative to the risk of concentrating in 3 volatile names. Momentum in a 10-stock universe is thin: the
  cross-section is too small for a reliable ranking.

Tally for this lab: 2 tests (B001, B002), 0 supported. With the earlier 36 tests across labs, still 0 supported.
