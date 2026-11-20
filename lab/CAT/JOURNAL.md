# Hypothesis Journal

Each entry is pre-registered, tested once out-of-sample, and kept whether it passed or failed.

## H001_news_overreaction — REJECTED
*CAT, tested 2026-10-16T13:42:28, costs 10 bps, split 2021-03-22*

**Hypothesis:** News overreaction: going long CAT for one session after a >2-sigma overnight gap DOWN, and short for one session after a >2-sigma gap UP or a high-attention (>2x volume) up day, earns positive returns with timing better than chance OOS.
**Rationale:** Sentiment shock mean-reverts: in-sample the rule averaged +0.54% per event (t=2.73, n=223); the same sign held on AXP, V, CAT and AAOI. Mechanism: liquidity providers are paid to absorb news-driven order imbalances. Satellite signal, so it is judged on timing, not vs buy&hold.

- In-sample  strategy: Sharpe +0.50 | CAGR +5.6% | MaxDD -45.8% | exposure 7% | position changes 379
- In-sample  buy&hold: Sharpe +0.49 | CAGR +11.5% | MaxDD -73.3% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe -0.55 | CAGR -5.7% | MaxDD -34.4% | exposure 7% | position changes 176**
- Out-of-sample buy&hold: Sharpe +0.89 | CAGR +25.7% | MaxDD -34.0% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.624  (Bonferroni alpha after 1 tests: 0.0500)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, min_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (OOS Sharpe -0.55, p=0.62) despite the strongest in-sample support (t=2.73). An in-sample t of 2.7 among ~20 sentiment rows across 5 stocks was not enough.

## H002_vol_target_replication — REJECTED
*CAT, tested 2026-10-16T13:42:30, costs 10 bps, split 2021-03-22*

**Hypothesis:** Replication of GOOGL H005: scaling CAT to a 25% annualised vol target (0.25 / realised 20d vol, cap 1) beats buy-and-hold OOS on both Sharpe and max drawdown, timing better than chance.
**Rationale:** GOOGL H005 beat buy&hold on Sharpe and drawdown OOS (p=0.18). The mechanism predicts it works where the highest-vol periods are not the best-return periods: in-sample CAT vol-Q5 next-day +0.130% vs all-days +0.066%. Identical rule, no re-tuning.

- In-sample  strategy: Sharpe +0.45 | CAGR +8.3% | MaxDD -50.9% | exposure 99% | position changes 1837
- In-sample  buy&hold: Sharpe +0.49 | CAGR +11.5% | MaxDD -73.3% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.87 | CAGR +21.2% | MaxDD -29.0% | exposure 100% | position changes 923**
- Out-of-sample buy&hold: Sharpe +0.89 | CAGR +25.7% | MaxDD -34.0% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.424  (Bonferroni alpha after 2 tests: 0.0250)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌, beat_buy_hold_drawdown=✅
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (p=0.42): drawdown -29% vs -34%, Sharpe 0.87 vs 0.89. Vol targeting again gave risk reduction without timing skill; 0 of 3 replications.

## H003_fear_filter — REJECTED
*CAT, tested 2026-10-16T13:43:55, costs 10 bps, split 2021-03-22*

**Hypothesis:** Fear filter: holding CAT except during the 20 sessions after the VIX z-score exceeds +1 beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** In-sample, 'buying fear' hurt quality large caps; the complement helped: CAT Sharpe 0.54 when avoiding post-fear windows vs 0.49 buy&hold (AXP 0.81 vs 0.45, V 0.91 vs 0.84, CAT 0.54 vs 0.49). Mechanism: elevated market fear clusters (vol persistence) and large caps with credit/cyclical exposure keep falling while it lasts. Same rule on AXP/V/CAT.

- In-sample  strategy: Sharpe +0.52 | CAGR +9.5% | MaxDD -53.4% | exposure 64% | position changes 57
- In-sample  buy&hold: Sharpe +0.49 | CAGR +11.5% | MaxDD -73.3% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.33 | CAGR +5.0% | MaxDD -40.7% | exposure 63% | position changes 24**
- Out-of-sample buy&hold: Sharpe +0.89 | CAGR +25.7% | MaxDD -34.0% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.890  (Bonferroni alpha after 3 tests: 0.0167)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.33 vs 0.89, p=0.89): same failure as AXP/V H003. 0 of 3 for the fear filter.

## H004_hype_fade — REJECTED
*CAT, tested 2026-10-16T13:45:05, costs 10 bps, split 2021-03-22*

**Hypothesis:** Hype-fade: holding CAT except for the 5 sessions after a high-attention up day (volume > 2x 50d median and close up) beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** The only sentiment rule that beat buy&hold in BOTH in-sample halves on AXP, V and CAT (CAT: 0.39 vs 0.35 / 0.70 vs 0.67). Mechanism: attention-driven buying is followed by giveback as the marginal buyer is exhausted. Caveat: overlaps with the short leg of H001 (news overreaction), which failed OOS, so the prior is lowered.

- In-sample  strategy: Sharpe +0.53 | CAGR +12.2% | MaxDD -68.3% | exposure 90% | position changes 109
- In-sample  buy&hold: Sharpe +0.49 | CAGR +11.5% | MaxDD -73.3% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.95 | CAGR +27.0% | MaxDD -32.8% | exposure 92% | position changes 42**
- Out-of-sample buy&hold: Sharpe +0.89 | CAGR +25.7% | MaxDD -34.0% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.160  (Bonferroni alpha after 4 tests: 0.0125)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=✅
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected on p (0.16): beat buy&hold OOS on Sharpe (0.95 vs 0.89) and drawdown (-33% vs -34%). But the identical rule failed on AXP and V, so 1 of 3 replications is most consistent with chance. CAT finished 0 of 4.

