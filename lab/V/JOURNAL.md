# Hypothesis Journal

Each entry is pre-registered, tested once out-of-sample, and kept whether it passed or failed.

## H001_news_overreaction — REJECTED
*V, tested 2026-10-16T13:42:25, costs 10 bps, split 2021-03-22*

**Hypothesis:** News overreaction: going long V for one session after a >2-sigma overnight gap DOWN, and short for one session after a >2-sigma gap UP or a high-attention (>2x volume) up day, earns positive returns with timing better than chance OOS.
**Rationale:** Sentiment shock mean-reverts: in-sample the rule averaged +0.30% per event (t=1.76, n=239); the same sign held on AXP, V, CAT and AAOI. Mechanism: liquidity providers are paid to absorb news-driven order imbalances. Satellite signal, so it is judged on timing, not vs buy&hold.

- In-sample  strategy: Sharpe +0.20 | CAGR +1.7% | MaxDD -35.8% | exposure 7% | position changes 402
- In-sample  buy&hold: Sharpe +0.84 | CAGR +23.0% | MaxDD -51.9% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe -1.38 | CAGR -9.2% | MaxDD -42.8% | exposure 6% | position changes 145**
- Out-of-sample buy&hold: Sharpe +0.68 | CAGR +13.5% | MaxDD -28.6% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.989  (Bonferroni alpha after 1 tests: 0.0500)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, min_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected decisively: OOS Sharpe -1.38, p=0.99. The overreaction reversed into continuation after 2021 (see AXP H001).

## H002_vol_target_replication — REJECTED
*V, tested 2026-10-16T13:42:26, costs 10 bps, split 2021-03-22*

**Hypothesis:** Replication of GOOGL H005: scaling V to a 25% annualised vol target (0.25 / realised 20d vol, cap 1) beats buy-and-hold OOS on both Sharpe and max drawdown, timing better than chance.
**Rationale:** GOOGL H005 beat buy&hold on Sharpe and drawdown OOS (p=0.18). The mechanism predicts it works where the highest-vol periods are not the best-return periods: in-sample V vol-Q5 next-day +0.081% vs all-days +0.100%. Identical rule, no re-tuning.

- In-sample  strategy: Sharpe +0.89 | CAGR +18.9% | MaxDD -33.5% | exposure 99% | position changes 1237
- In-sample  buy&hold: Sharpe +0.84 | CAGR +23.0% | MaxDD -51.9% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.64 | CAGR +11.8% | MaxDD -29.4% | exposure 100% | position changes 346**
- Out-of-sample buy&hold: Sharpe +0.68 | CAGR +13.5% | MaxDD -28.6% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.651  (Bonferroni alpha after 2 tests: 0.0250)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌, beat_buy_hold_drawdown=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (p=0.65); worse on both Sharpe and drawdown. GOOGL vol-targeting does not replicate on V, the most GOOGL-like stock here.

## H003_fear_filter — REJECTED
*V, tested 2026-10-16T13:43:53, costs 10 bps, split 2021-03-22*

**Hypothesis:** Fear filter: holding V except during the 20 sessions after the VIX z-score exceeds +1 beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** In-sample, 'buying fear' hurt quality large caps; the complement helped: V Sharpe 0.91 when avoiding post-fear windows vs 0.84 buy&hold (AXP 0.81 vs 0.45, V 0.91 vs 0.84, CAT 0.54 vs 0.49). Mechanism: elevated market fear clusters (vol persistence) and large caps with credit/cyclical exposure keep falling while it lasts. Same rule on AXP/V/CAT.

- In-sample  strategy: Sharpe +0.89 | CAGR +16.0% | MaxDD -23.0% | exposure 64% | position changes 57
- In-sample  buy&hold: Sharpe +0.84 | CAGR +23.0% | MaxDD -51.9% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe -0.11 | CAGR -2.8% | MaxDD -41.4% | exposure 63% | position changes 24**
- Out-of-sample buy&hold: Sharpe +0.68 | CAGR +13.5% | MaxDD -28.6% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 1.000  (Bonferroni alpha after 3 tests: 0.0167)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe -0.11, p=1.00): same failure as AXP H003, exiting at fear peaks and missing rebounds.

## H004_hype_fade — REJECTED
*V, tested 2026-10-16T13:45:03, costs 10 bps, split 2021-03-22*

**Hypothesis:** Hype-fade: holding V except for the 5 sessions after a high-attention up day (volume > 2x 50d median and close up) beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** The only sentiment rule that beat buy&hold in BOTH in-sample halves on AXP, V and CAT (V: 0.84 vs 0.75 / 1.05 vs 0.97). Mechanism: attention-driven buying is followed by giveback as the marginal buyer is exhausted. Caveat: overlaps with the short leg of H001 (news overreaction), which failed OOS, so the prior is lowered.

- In-sample  strategy: Sharpe +0.91 | CAGR +23.9% | MaxDD -45.8% | exposure 89% | position changes 121
- In-sample  buy&hold: Sharpe +0.84 | CAGR +23.0% | MaxDD -51.9% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.57 | CAGR +10.5% | MaxDD -34.1% | exposure 91% | position changes 46**
- Out-of-sample buy&hold: Sharpe +0.68 | CAGR +13.5% | MaxDD -28.6% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.626  (Bonferroni alpha after 4 tests: 0.0125)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.57 vs 0.68, p=0.63). V finished 0 of 4. Payment-network compounders behaved like GOOGL: hard to beat by stepping aside.

