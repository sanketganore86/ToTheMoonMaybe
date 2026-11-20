# Hypothesis Journal

Each entry is pre-registered, tested once out-of-sample, and kept whether it passed or failed.

## H001_trend_ma200 — REJECTED
*MRNA, tested 2026-10-16T13:25:23, costs 10 bps, split 2024-06-06*

**Hypothesis:** Holding MRNA only while Close > 200-day SMA beats buy-and-hold OOS on both Sharpe and max drawdown, with timing better than chance.
**Rationale:** Weekly candles: one giant bubble-and-crash (COVID vaccine boom, then -86%). In-sample forward 20d return +11.1% above MA200 vs +0.7% below. Narrative-driven biotech should trend.

- In-sample  strategy: Sharpe +1.09 | CAGR +60.2% | MaxDD -66.1% | exposure 48% | position changes 25
- In-sample  buy&hold: Sharpe +0.89 | CAGR +47.2% | MaxDD -85.7% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.88 | CAGR +94.4% | MaxDD -39.2% | exposure 43% | position changes 2**
- Out-of-sample buy&hold: Sharpe +0.53 | CAGR +15.7% | MaxDD -85.5% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.199  (Bonferroni alpha after 1 tests: 0.0500)
- Checks: no_lookahead=✅, p_value=❌, min_trades=❌, beat_buy_hold_sharpe=✅, beat_buy_hold_drawdown=✅
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected on min_trades: only 2 position changes OOS. The candle chart shows one exit in Aug 2024 (~$95), which avoided the slide to ~$25, and one re-entry in Dec 2025 that caught the rally to ~$230. +94% CAGR, but n=1 round trip is luck, not evidence. Next: a faster trend rule that trades often enough to be tested.

## H002_three_soldiers — REJECTED
*MRNA, tested 2026-10-16T13:25:25, costs 10 bps, split 2024-06-06*

**Hypothesis:** Holding MRNA for 5 sessions after a three-white-soldiers candle pattern beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** In-sample: 5d forward return +3.98% after the pattern vs +1.35% baseline, 65% up (n=124). Short-term momentum in a news-driven stock. The daily candle chart shows runs of green candles into the May-2024 breakout.

- In-sample  strategy: Sharpe +1.19 | CAGR +48.1% | MaxDD -55.2% | exposure 27% | position changes 106
- In-sample  buy&hold: Sharpe +0.89 | CAGR +47.2% | MaxDD -85.7% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.46 | CAGR +17.4% | MaxDD -49.2% | exposure 32% | position changes 59**
- Out-of-sample buy&hold: Sharpe +0.53 | CAGR +15.7% | MaxDD -85.5% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.296  (Bonferroni alpha after 2 tests: 0.0250)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.46 vs 0.53, p=0.30). It did cut drawdown (-49% vs -86%) only because it was 68% flat.

## H003_monday_replication — REJECTED
*MRNA, tested 2026-10-16T13:25:27, costs 10 bps, split 2024-06-06*

**Hypothesis:** Replication of TSLA H003: holding MRNA only on Mondays beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** Cross-asset check of the TSLA near-miss. MRNA in-sample Monday +0.64% (t=+1.87).

- In-sample  strategy: Sharpe +0.17 | CAGR -1.2% | MaxDD -64.9% | exposure 20% | position changes 554
- In-sample  buy&hold: Sharpe +0.89 | CAGR +47.2% | MaxDD -85.7% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe -0.14 | CAGR -7.4% | MaxDD -31.0% | exposure 20% | position changes 236**
- Out-of-sample buy&hold: Sharpe +0.53 | CAGR +15.7% | MaxDD -85.5% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.484  (Bonferroni alpha after 3 tests: 0.0167)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe -0.14, p=0.48). Monday effect does not replicate on MRNA either: 0 of 3 replications, so it is dead.

## H004_trend_50_band — REJECTED
*MRNA, tested 2026-10-16T13:26:25, costs 10 bps, split 2024-06-06*

**Hypothesis:** A 50-day trend filter with a +/-5% band (enter above 1.05*SMA50, exit below 0.95*SMA50) beats buy-and-hold OOS on Sharpe and drawdown with timing better than chance, with at least 10 position changes.
**Rationale:** H001 looked spectacular but traded once. MRNA trends strongly (in-sample MA50: +8.3% fwd 20d above vs +1.9% below); a faster rule trades enough to be testable, and the band limits whipsaw seen on TSLA/AMD.

- In-sample  strategy: Sharpe +0.98 | CAGR +49.8% | MaxDD -60.4% | exposure 54% | position changes 27
- In-sample  buy&hold: Sharpe +0.89 | CAGR +47.2% | MaxDD -85.7% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.61 | CAGR +37.7% | MaxDD -61.3% | exposure 43% | position changes 16**
- Out-of-sample buy&hold: Sharpe +0.53 | CAGR +15.7% | MaxDD -85.5% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.233  (Bonferroni alpha after 4 tests: 0.0125)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=✅, beat_buy_hold_drawdown=✅
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected on p-value only (0.23): beat buy&hold on Sharpe (0.61 vs 0.53) and drawdown (-61% vs -86%) with 16 position changes, so it is now testable, unlike H001. Most of the gain is being flat during the 2024-25 collapse, which a random-timing null with 43% exposure also often captures. Stopping MRNA here: the remaining idea (volume breakouts) showed no in-sample edge (+6.4% vs +5.7% baseline fwd 20d), and the in-sample vol profile matches TSLA's, where vol-targeting failed.

