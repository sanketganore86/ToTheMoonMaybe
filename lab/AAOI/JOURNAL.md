# Hypothesis Journal

Each entry is pre-registered, tested once out-of-sample, and kept whether it passed or failed.

## H001_news_overreaction — REJECTED
*AAOI, tested 2026-10-16T13:42:32, costs 10 bps, split 2022-11-10*

**Hypothesis:** News overreaction: going long AAOI for one session after a >2-sigma overnight gap DOWN, and short for one session after a >2-sigma gap UP or a high-attention (>2x volume) up day, earns positive returns with timing better than chance OOS.
**Rationale:** Sentiment shock mean-reverts: in-sample the rule averaged +0.46% per event (t=0.98, n=211); the same sign held on AXP, V, CAT and AAOI. Mechanism: liquidity providers are paid to absorb news-driven order imbalances. Satellite signal, so it is judged on timing, not vs buy&hold.

- In-sample  strategy: Sharpe +0.21 | CAGR +1.9% | MaxDD -75.6% | exposure 9% | position changes 314
- In-sample  buy&hold: Sharpe +0.12 | CAGR -15.7% | MaxDD -98.5% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe -0.72 | CAGR -46.0% | MaxDD -92.6% | exposure 13% | position changes 168**
- Out-of-sample buy&hold: Sharpe +1.32 | CAGR +150.2% | MaxDD -77.2% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.740  (Bonferroni alpha after 1 tests: 0.0500)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, min_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (OOS Sharpe -0.72, p=0.74). Same reversal-to-momentum flip as the large caps; in a stock that rose 150%/yr OOS, shorting news pops was costly.

## H002_avoid_complacency — REJECTED
*AAOI, tested 2026-10-16T13:42:34, costs 10 bps, split 2022-11-10*

**Hypothesis:** Holding AAOI only when the VIX term structure is NOT complacent (VIX/VIX3M >= 0.85) beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** Speculative stocks lagged during market complacency in-sample: AAOI fwd-20d -0.98% when VIX/VIX3M < 0.85 vs +0.76% on all days; the same held for ASTS (-4.84% vs +8.76%). Mechanism: complacent markets precede risk-off rotations that hit high-beta speculative names hardest, while fear periods precede sharp rebounds.

- In-sample  strategy: Sharpe +0.16 | CAGR -6.2% | MaxDD -92.4% | exposure 64% | position changes 283
- In-sample  buy&hold: Sharpe +0.12 | CAGR -15.7% | MaxDD -98.5% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +1.28 | CAGR +134.1% | MaxDD -66.4% | exposure 75% | position changes 134**
- Out-of-sample buy&hold: Sharpe +1.32 | CAGR +150.2% | MaxDD -77.2% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.263  (Bonferroni alpha after 2 tests: 0.0250)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (p=0.26): Sharpe 1.28 vs 1.32, drawdown -66% vs -77%. Risk reduction again, no timing skill. Its replication pair ASTS H001 also failed.

## H003_buy_credit_panic — REJECTED
*AAOI, tested 2026-10-16T13:43:57, costs 10 bps, split 2022-11-10*

**Hypothesis:** Contrarian: holding AAOI only during the 20 sessions after credit markets turn risk-off (HYG/LQD more than 1% below its 50d mean) beats buy-and-hold OOS Sharpe, timing better than chance.
**Rationale:** Opposite of the large-cap fear filter: in-sample AAOI Sharpe 0.47 holding after credit stress vs 0.12 buy&hold (complement -0.25); fwd 20d +4.7% vs +0.8%. Mechanism: speculative small caps get indiscriminately dumped in risk-off episodes and rebound hardest.

- In-sample  strategy: Sharpe +0.47 | CAGR +11.6% | MaxDD -65.8% | exposure 45% | position changes 42
- In-sample  buy&hold: Sharpe +0.12 | CAGR -15.7% | MaxDD -98.5% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.49 | CAGR +11.7% | MaxDD -62.4% | exposure 35% | position changes 16**
- Out-of-sample buy&hold: Sharpe +1.32 | CAGR +150.2% | MaxDD -77.2% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.701  (Bonferroni alpha after 3 tests: 0.0167)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.49 vs 1.32, p=0.70); only 35% exposure in a stock that rose 150%/yr. Split-half screening afterwards showed this idea was unstable in-sample (H1 0.64 vs B&H 0.71), so that check would have filtered it out. Stopping AAOI: no remaining idea beat buy&hold in both in-sample halves.

