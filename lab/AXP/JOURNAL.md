# Hypothesis Journal

Each entry is pre-registered, tested once out-of-sample, and kept whether it passed or failed.

## H001_news_overreaction — REJECTED
*AXP, tested 2026-10-16T13:42:21, costs 10 bps, split 2021-03-22*

**Hypothesis:** News overreaction: going long AXP for one session after a >2-sigma overnight gap DOWN, and short for one session after a >2-sigma gap UP or a high-attention (>2x volume) up day, earns positive returns with timing better than chance OOS.
**Rationale:** Sentiment shock mean-reverts: in-sample the rule averaged +0.30% per event (t=1.21, n=220); the same sign held on AXP, V, CAT and AAOI. Mechanism: liquidity providers are paid to absorb news-driven order imbalances. Satellite signal, so it is judged on timing, not vs buy&hold.

- In-sample  strategy: Sharpe +0.14 | CAGR +1.0% | MaxDD -52.6% | exposure 7% | position changes 371
- In-sample  buy&hold: Sharpe +0.45 | CAGR +10.7% | MaxDD -79.6% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe -0.33 | CAGR -4.1% | MaxDD -37.5% | exposure 7% | position changes 156**
- Out-of-sample buy&hold: Sharpe +0.69 | CAGR +17.0% | MaxDD -31.5% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.403  (Bonferroni alpha after 1 tests: 0.0500)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, min_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected: the in-sample reversal (+0.30%/event) flipped OOS (Sharpe -0.33). The same flip happened on V, CAT and AAOI, so post-2021 news moves *continued* rather than reverted. Costs (~20 bps per event) had already eaten most of the in-sample edge (IS Sharpe only 0.14). Testing 'news momentum' now would use OOS knowledge, so it needs fresh data (paper trading).

## H002_vol_target_replication — REJECTED
*AXP, tested 2026-10-16T13:42:23, costs 10 bps, split 2021-03-22*

**Hypothesis:** Replication of GOOGL H005: scaling AXP to a 25% annualised vol target (0.25 / realised 20d vol, cap 1) beats buy-and-hold OOS on both Sharpe and max drawdown, timing better than chance.
**Rationale:** GOOGL H005 beat buy&hold on Sharpe and drawdown OOS (p=0.18). The mechanism predicts it works where the highest-vol periods are not the best-return periods: in-sample AXP vol-Q5 next-day +0.076% vs all-days +0.070%. Identical rule, no re-tuning.

- In-sample  strategy: Sharpe +0.58 | CAGR +11.0% | MaxDD -43.5% | exposure 99% | position changes 1304
- In-sample  buy&hold: Sharpe +0.45 | CAGR +10.7% | MaxDD -79.6% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.57 | CAGR +11.8% | MaxDD -27.7% | exposure 100% | position changes 768**
- Out-of-sample buy&hold: Sharpe +0.69 | CAGR +17.0% | MaxDD -31.5% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.925  (Bonferroni alpha after 2 tests: 0.0250)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌, beat_buy_hold_drawdown=✅
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (p=0.93). Cut drawdown (-28% vs -32%) but lost Sharpe. GOOGL H005 failed to replicate here, on V or on CAT, so it was most likely luck.

## H003_fear_filter — REJECTED
*AXP, tested 2026-10-16T13:43:51, costs 10 bps, split 2021-03-22*

**Hypothesis:** Fear filter: holding AXP except during the 20 sessions after the VIX z-score exceeds +1 beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** In-sample, 'buying fear' hurt quality large caps; the complement helped: AXP Sharpe 0.81 when avoiding post-fear windows vs 0.45 buy&hold (AXP 0.81 vs 0.45, V 0.91 vs 0.84, CAT 0.54 vs 0.49). Mechanism: elevated market fear clusters (vol persistence) and large caps with credit/cyclical exposure keep falling while it lasts. Same rule on AXP/V/CAT.

- In-sample  strategy: Sharpe +0.79 | CAGR +17.8% | MaxDD -38.7% | exposure 64% | position changes 57
- In-sample  buy&hold: Sharpe +0.45 | CAGR +10.7% | MaxDD -79.6% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe -0.00 | CAGR -2.0% | MaxDD -41.3% | exposure 63% | position changes 24**
- Out-of-sample buy&hold: Sharpe +0.69 | CAGR +17.0% | MaxDD -31.5% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.995  (Bonferroni alpha after 3 tests: 0.0167)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected, worse than random (OOS Sharpe 0.00, p=0.995). The OOS candle chart shows why: VIX z-scores peak *after* a sell-off, so the filter exited near lows (2022, Aug 2024, Apr 2025) and sat flat through V-shaped rebounds. In-sample (incl. 2008) fear kept compounding; in 2021-26 fear was bought immediately. The rule was stable in both in-sample halves, so this is a genuine regime change, not a screening failure.

## H004_hype_fade — REJECTED
*AXP, tested 2026-10-16T13:44:59, costs 10 bps, split 2021-03-22*

**Hypothesis:** Hype-fade: holding AXP except for the 5 sessions after a high-attention up day (volume > 2x 50d median and close up) beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** The only sentiment rule that beat buy&hold in BOTH in-sample halves on AXP, V and CAT (AXP: 0.62 vs 0.48 / 0.63 vs 0.43). Mechanism: attention-driven buying is followed by giveback as the marginal buyer is exhausted. Caveat: overlaps with the short leg of H001 (news overreaction), which failed OOS, so the prior is lowered.

- In-sample  strategy: Sharpe +0.60 | CAGR +16.3% | MaxDD -71.4% | exposure 92% | position changes 85
- In-sample  buy&hold: Sharpe +0.45 | CAGR +10.7% | MaxDD -79.6% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.48 | CAGR +9.8% | MaxDD -33.6% | exposure 90% | position changes 50**
- Out-of-sample buy&hold: Sharpe +0.69 | CAGR +17.0% | MaxDD -31.5% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.842  (Bonferroni alpha after 4 tests: 0.0125)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.48 vs 0.69, p=0.84). Passed split-half screening in-sample but not OOS. Consistent with the H001 OOS finding that post-2021 news and attention moves continue rather than fade.

## H005_market_regime — REJECTED
*AXP, tested 2026-10-16T13:45:01, costs 10 bps, split 2021-03-22*

**Hypothesis:** Holding AXP only while SPY is above its 200-day SMA beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** AXP is a credit-sensitive financial; the broad market regime beat buy&hold in both in-sample halves (0.72 vs 0.48, 0.60 vs 0.43). Slower than the VIX fear filter (H003), so it should not exit at short panic peaks. The failed H003 lowers the prior.

- In-sample  strategy: Sharpe +0.66 | CAGR +12.8% | MaxDD -34.3% | exposure 79% | position changes 65
- In-sample  buy&hold: Sharpe +0.45 | CAGR +10.7% | MaxDD -79.6% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.64 | CAGR +12.7% | MaxDD -27.0% | exposure 80% | position changes 30**
- Out-of-sample buy&hold: Sharpe +0.69 | CAGR +17.0% | MaxDD -31.5% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.381  (Bonferroni alpha after 5 tests: 0.0100)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.64 vs 0.69, p=0.38). Lower drawdown (-27% vs -32%) at 80% exposure: risk reduction, no timing skill. AXP finished 0 of 5. Summary: every sentiment and regime rule that worked 2008-2021 either reversed or diluted in 2021-2026.

