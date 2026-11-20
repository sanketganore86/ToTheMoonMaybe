# Hypothesis Journal

Each entry is pre-registered, tested once out-of-sample, and kept whether it passed or failed.

## H001_trend_ma200 — REJECTED
*AMD, tested 2026-10-16T13:25:18, costs 10 bps, split 2020-02-21*

**Hypothesis:** Holding AMD only while Close > 200-day SMA beats buy-and-hold OOS on both Sharpe and max drawdown, with timing better than chance.
**Rationale:** Weekly candles show multi-year regimes (2006-2015 collapse of -96%, 2016+ boom). In-sample forward 20d return +4.3% above MA200 vs -0.3% below. Also the cross-asset check of TSLA H001, which failed on whipsaw.

- In-sample  strategy: Sharpe +0.68 | CAGR +21.7% | MaxDD -65.8% | exposure 50% | position changes 73
- In-sample  buy&hold: Sharpe +0.46 | CAGR +10.8% | MaxDD -96.2% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.72 | CAGR +26.2% | MaxDD -54.7% | exposure 70% | position changes 50**
- Out-of-sample buy&hold: Sharpe +0.87 | CAGR +39.8% | MaxDD -65.4% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.411  (Bonferroni alpha after 1 tests: 0.0500)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌, beat_buy_hold_drawdown=✅
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected on Sharpe (0.72 vs 0.87) and p=0.41, though drawdown improved (-55% vs -65%). OOS candle chart shows clusters of whipsaw trades around MA200 in 2021, 2022, 2023-24, the same failure as TSLA H001. Next: a hysteresis band so small crossings don't trigger trades.

## H002_crash_avoid — REJECTED
*AMD, tested 2026-10-16T13:25:20, costs 10 bps, split 2020-02-21*

**Hypothesis:** Holding AMD except for the 5 sessions after a -2 sigma down day beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** In-sample, after big DOWN days AMD's next-day mean was -0.78% (t=-1.6) vs +0.11% normally: crashes continue (forced selling, analyst downgrades follow).

- In-sample  strategy: Sharpe +0.60 | CAGR +19.8% | MaxDD -92.7% | exposure 89% | position changes 147
- In-sample  buy&hold: Sharpe +0.46 | CAGR +10.8% | MaxDD -96.2% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.70 | CAGR +25.7% | MaxDD -64.3% | exposure 88% | position changes 72**
- Out-of-sample buy&hold: Sharpe +0.87 | CAGR +39.8% | MaxDD -65.4% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.747  (Bonferroni alpha after 2 tests: 0.0250)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.70, p=0.75). Stepping aside after crashes mostly missed the rebounds; in-sample crash continuation (t=-1.6) was never significant.

## H003_monday_replication — REJECTED
*AMD, tested 2026-10-16T13:25:22, costs 10 bps, split 2020-02-21*

**Hypothesis:** Replication of TSLA H003: holding AMD only on Mondays beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** Cross-asset check of the TSLA near-miss. AMD in-sample Monday +0.18% (t=+1.37).

- In-sample  strategy: Sharpe +0.02 | CAGR -2.8% | MaxDD -88.1% | exposure 20% | position changes 1568
- In-sample  buy&hold: Sharpe +0.46 | CAGR +10.8% | MaxDD -96.2% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.41 | CAGR +7.4% | MaxDD -37.8% | exposure 20% | position changes 666**
- Out-of-sample buy&hold: Sharpe +0.87 | CAGR +39.8% | MaxDD -65.4% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.117  (Bonferroni alpha after 3 tests: 0.0167)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.41, p=0.12). Monday effect does not replicate on AMD.

## H004_trend_band — REJECTED
*AMD, tested 2026-10-16T13:26:24, costs 10 bps, split 2020-02-21*

**Hypothesis:** A 200-day trend filter with a +/-5% hysteresis band (enter above 1.05*SMA200, exit below 0.95*SMA200) beats buy-and-hold OOS on Sharpe and drawdown with timing better than chance.
**Rationale:** H001's OOS candle chart showed losses came from whipsaw clusters at the MA. A band ignores small crossings while still exiting multi-month busts like 2022.

- In-sample  strategy: Sharpe +0.75 | CAGR +25.2% | MaxDD -57.1% | exposure 50% | position changes 23
- In-sample  buy&hold: Sharpe +0.46 | CAGR +10.8% | MaxDD -96.2% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.80 | CAGR +30.4% | MaxDD -55.4% | exposure 68% | position changes 14**
- Out-of-sample buy&hold: Sharpe +0.87 | CAGR +39.8% | MaxDD -65.4% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.295  (Bonferroni alpha after 4 tests: 0.0125)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌, beat_buy_hold_drawdown=✅
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.80 vs 0.87, p=0.30), but the band cut position changes to 14 (from 50) and improved Sharpe vs H001 (0.80 vs 0.72), with a lower drawdown (-55% vs -65%). It still has no significant timing skill. Next: use the semiconductor sector (SMH) as the regime signal; in-sample AMD next-day +0.18% (t=2.9) when SMH > MA200 vs -0.10% below.

## H005_sector_regime — REJECTED
*AMD, tested 2026-10-16T13:27:26, costs 10 bps, split 2020-02-21*

**Hypothesis:** Holding AMD only while the semiconductor ETF SMH is in an uptrend (enter SMH > 1.03*SMA200, exit SMH < 0.97*SMA200) beats buy-and-hold OOS on Sharpe and drawdown with timing better than chance.
**Rationale:** AMD is a high-beta semis name; the sector cycle drives it. In-sample AMD next-day +0.18% (t=2.9) when SMH > MA200 vs -0.10% below. The smoother sector ETF plus a 3% band should avoid the own-price whipsaw seen in H001.

- In-sample  strategy: Sharpe +0.65 | CAGR +20.6% | MaxDD -77.4% | exposure 68% | position changes 27
- In-sample  buy&hold: Sharpe +0.46 | CAGR +10.8% | MaxDD -96.2% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.85 | CAGR +34.3% | MaxDD -51.9% | exposure 82% | position changes 10**
- Out-of-sample buy&hold: Sharpe +0.87 | CAGR +39.8% | MaxDD -65.4% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.290  (Bonferroni alpha after 5 tests: 0.0100)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌, beat_buy_hold_drawdown=✅
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.85 vs 0.87, p=0.29); drawdown improved (-52% vs -65%). Best AMD variant so far: sector regime > own-price trend (H001 0.72) > band (H004 0.80), but still no timing skill. Across all 5 AMD tests: risk-reduction rules consistently cut drawdowns 10-15 points and give up some return; none adds timing alpha.

