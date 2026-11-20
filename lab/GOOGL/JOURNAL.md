# Hypothesis Journal

Each entry is pre-registered, tested once out-of-sample, and kept whether it passed or failed.

## H001_dip_buy_52w — REJECTED
*GOOGL, tested 2026-10-16T13:25:13, costs 10 bps, split 2020-02-21*

**Hypothesis:** Holding GOOGL only while it is >10% below its 252-day high (dip-buying) earns a higher OOS Sharpe than buy-and-hold, with timing better than chance.
**Rationale:** In-sample GOOGL is a steady compounder (weekly candles: shallow pullbacks that recover); forward 20d returns were HIGHER below MA200 (+2.0%) than above (+1.4%), suggesting overreaction on dips in a quality name.

- In-sample  strategy: Sharpe +0.56 | CAGR +10.2% | MaxDD -60.9% | exposure 36% | position changes 168
- In-sample  buy&hold: Sharpe +0.88 | CAGR +24.6% | MaxDD -65.3% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.43 | CAGR +7.8% | MaxDD -37.5% | exposure 41% | position changes 67**
- Out-of-sample buy&hold: Sharpe +0.86 | CAGR +25.6% | MaxDD -44.3% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.602  (Bonferroni alpha after 1 tests: 0.0500)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (OOS Sharpe 0.43 vs 0.86, p=0.60). Candle chart of 2022-23 shows why: '10% below the 52w high' stayed true through the whole 2022 bear market, so it bought all the way down. Dip-buying without trend context is catching a falling knife. Next: buy pullbacks only *inside* an uptrend.

## H002_inside_bar — REJECTED
*GOOGL, tested 2026-10-16T13:25:15, costs 10 bps, split 2020-02-21*

**Hypothesis:** Holding GOOGL for the session after an inside-bar candle (flat otherwise) earns a higher OOS Sharpe than buy-and-hold with timing better than chance.
**Rationale:** Only candlestick pattern with |t|>2 in-sample across GOOGL/AMD/MRNA (next-day +0.17%, t=2.17, n=486). 1 hit in 30 pattern tests is what chance predicts, so this is primarily a data-mining check. Mechanism: volatility compression before expansion.

- In-sample  strategy: Sharpe -0.06 | CAGR -1.0% | MaxDD -28.4% | exposure 12% | position changes 926
- In-sample  buy&hold: Sharpe +0.88 | CAGR +24.6% | MaxDD -65.3% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.01 | CAGR -0.5% | MaxDD -16.7% | exposure 11% | position changes 366**
- Out-of-sample buy&hold: Sharpe +0.86 | CAGR +25.6% | MaxDD -44.3% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.274  (Bonferroni alpha after 2 tests: 0.0250)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.01, p=0.27). The in-sample t=2.17 was the 1-in-30 chance hit we expected; it vanished OOS. Classic candlestick patterns showed no reliable edge on any of the 3 tickers.

## H003_monday_replication — REJECTED
*GOOGL, tested 2026-10-16T13:25:17, costs 10 bps, split 2020-02-21*

**Hypothesis:** Replication of TSLA H003: holding GOOGL only on Mondays beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** TSLA showed a Monday effect (OOS p=0.057). A real weekend effect should replicate on other stocks. GOOGL in-sample Monday was weak (t=+0.47), so prior is low.

- In-sample  strategy: Sharpe -0.59 | CAGR -8.6% | MaxDD -86.3% | exposure 20% | position changes 1568
- In-sample  buy&hold: Sharpe +0.88 | CAGR +24.6% | MaxDD -65.3% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe -0.17 | CAGR -3.4% | MaxDD -47.6% | exposure 20% | position changes 666**
- Out-of-sample buy&hold: Sharpe +0.86 | CAGR +25.6% | MaxDD -44.3% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.345  (Bonferroni alpha after 3 tests: 0.0167)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe -0.17, p=0.35). Monday effect does not replicate on GOOGL, so TSLA H003's near-miss was most likely noise.

## H004_pullback_in_uptrend — REJECTED
*GOOGL, tested 2026-10-16T13:26:22, costs 10 bps, split 2020-02-21*

**Hypothesis:** Holding GOOGL for 10 sessions after it closes at a 10-day low WHILE above its 200-day SMA beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** H001 failed by buying into a bear market. Restricting dip-buys to an established uptrend keeps the overreaction mechanism but avoids falling knives.

- In-sample  strategy: Sharpe +0.37 | CAGR +4.8% | MaxDD -52.1% | exposure 38% | position changes 174
- In-sample  buy&hold: Sharpe +0.88 | CAGR +24.6% | MaxDD -65.3% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.70 | CAGR +12.7% | MaxDD -24.9% | exposure 39% | position changes 82**
- Out-of-sample buy&hold: Sharpe +0.86 | CAGR +25.6% | MaxDD -44.3% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.259  (Bonferroni alpha after 4 tests: 0.0125)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.70 vs 0.86, p=0.26), but the fix worked as intended: max drawdown fell from -37.5% (H001) to -24.9% against -44.3% for buy&hold, at 39% exposure. Not enough timing skill to beat holding a strong compounder. Next: GOOGL differs from TSLA in that high vol is NOT rewarded (in-sample Q5 vol next-day +0.10% vs Q3 +0.19%), so volatility targeting, which failed on TSLA, has a real mechanism here.

## H005_vol_target — REJECTED
*GOOGL, tested 2026-10-16T13:27:24, costs 10 bps, split 2020-02-21*

**Hypothesis:** Scaling GOOGL to a 25% annualised vol target (0.25 / realised 20d vol, cap 1) beats buy-and-hold OOS on both Sharpe and max drawdown, with timing better than chance.
**Rationale:** Unlike TSLA, GOOGL's highest-vol quintile does not have the highest next-day returns (Q5 +0.10% vs Q3 +0.19%), so cutting exposure in vol spikes should remove risk more than return. In-sample Sharpe 0.88 -> 0.99. Mechanism: Moreira-Muir vol-managed portfolios.

- In-sample  strategy: Sharpe +0.98 | CAGR +22.6% | MaxDD -51.1% | exposure 99% | position changes 1647
- In-sample  buy&hold: Sharpe +0.88 | CAGR +24.6% | MaxDD -65.3% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.91 | CAGR +22.3% | MaxDD -36.5% | exposure 100% | position changes 1132**
- Out-of-sample buy&hold: Sharpe +0.86 | CAGR +25.6% | MaxDD -44.3% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.178  (Bonferroni alpha after 5 tests: 0.0100)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=✅, beat_buy_hold_drawdown=✅
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected on p-value (0.18) only. This is the best result in the whole lab: it beat buy&hold OOS on Sharpe (0.91 vs 0.86) and drawdown (-36.5% vs -44.3%), consistent with in-sample (0.98 vs 0.88) and with the mechanism predicted *before* testing, which is opposite to TSLA H002, as the vol-quintile table said it would be. The edge is real-looking but small; a ~0.05 Sharpe gain cannot be distinguished from luck in 6.6 years. Best candidate for a cross-asset replication on other low-vol large caps (MSFT, AAPL, SPY).

