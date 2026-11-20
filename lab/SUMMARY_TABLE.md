# Results across all labs

## Position strategies (vs buy & hold, out-of-sample)

| Ticker | Hypothesis | MaxDD | B&H MaxDD | Sharpe | B&H Sharpe | p | Edge verdict | Protection | Safe exposure |
|---|---|---|---|---|---|---|---|---|---|
| AAOI | H001_news_overreaction | -93% | -77% | -0.72 | +1.32 | 0.74 | REJECTED | PASS ONLY WHEN SIZED DOWN | 4% |
| AAOI | H002_avoid_complacency | -66% | -77% | +1.28 | +1.32 | 0.26 | REJECTED | PASS ONLY WHEN SIZED DOWN | 5% |
| AAOI | H003_buy_credit_panic | -62% | -77% | +0.49 | +1.32 | 0.70 | REJECTED | PASS ONLY WHEN SIZED DOWN | 7% |
| AMD | H001_trend_ma200 | -55% | -65% | +0.72 | +0.87 | 0.41 | REJECTED | PASS ONLY WHEN SIZED DOWN | 8% |
| AMD | H002_crash_avoid | -64% | -65% | +0.70 | +0.87 | 0.75 | REJECTED | PASS ONLY WHEN SIZED DOWN | 5% |
| AMD | H003_monday_replication | -38% | -65% | +0.41 | +0.87 | 0.12 | REJECTED | PASS ONLY WHEN SIZED DOWN | 6% |
| AMD | H004_trend_band | -55% | -65% | +0.80 | +0.87 | 0.30 | REJECTED | PASS ONLY WHEN SIZED DOWN | 8% |
| AMD | H005_sector_regime | -52% | -65% | +0.85 | +0.87 | 0.29 | REJECTED | PASS ONLY WHEN SIZED DOWN | 8% |
| ASTS | H001_avoid_complacency | -66% | -69% | +0.26 | +0.67 | 0.73 | REJECTED | PASS ONLY WHEN SIZED DOWN | 8% |
| AXP | H001_news_overreaction | -38% | -32% | -0.33 | +0.69 | 0.40 | REJECTED | PASS ONLY WHEN SIZED DOWN | 15% |
| AXP | H002_vol_target_replication | -28% | -32% | +0.57 | +0.69 | 0.92 | REJECTED | PASS ONLY WHEN SIZED DOWN | 17% |
| AXP | H003_fear_filter | -41% | -32% | -0.00 | +0.69 | 1.00 | REJECTED | PASS ONLY WHEN SIZED DOWN | 15% |
| AXP | H004_hype_fade | -34% | -32% | +0.48 | +0.69 | 0.84 | REJECTED | PASS ONLY WHEN SIZED DOWN | 10% |
| AXP | H005_market_regime | -27% | -32% | +0.64 | +0.69 | 0.38 | REJECTED | PASS ONLY WHEN SIZED DOWN | 23% |
| CAT | H001_news_overreaction | -34% | -34% | -0.55 | +0.89 | 0.62 | REJECTED | PASS ONLY WHEN SIZED DOWN | 14% |
| CAT | H002_vol_target_replication | -29% | -34% | +0.87 | +0.89 | 0.42 | REJECTED | PASS ONLY WHEN SIZED DOWN | 15% |
| CAT | H003_fear_filter | -41% | -34% | +0.33 | +0.89 | 0.89 | REJECTED | PASS ONLY WHEN SIZED DOWN | 15% |
| CAT | H004_hype_fade | -33% | -34% | +0.95 | +0.89 | 0.16 | REJECTED | PASS ONLY WHEN SIZED DOWN | 10% |
| GOOGL | H001_dip_buy_52w | -38% | -44% | +0.43 | +0.86 | 0.60 | REJECTED | PASS ONLY WHEN SIZED DOWN | 13% |
| GOOGL | H002_inside_bar | -17% | -44% | +0.01 | +0.86 | 0.27 | REJECTED | PASS ONLY WHEN SIZED DOWN | 27% |
| GOOGL | H003_monday_replication | -48% | -44% | -0.17 | +0.86 | 0.35 | REJECTED | PASS ONLY WHEN SIZED DOWN | 4% |
| GOOGL | H004_pullback_in_uptrend | -25% | -44% | +0.70 | +0.86 | 0.26 | REJECTED | PASS ONLY WHEN SIZED DOWN | 16% |
| GOOGL | H005_vol_target | -36% | -44% | +0.91 | +0.86 | 0.18 | REJECTED | PASS ONLY WHEN SIZED DOWN | 16% |
| MRNA | H001_trend_ma200 | -39% | -86% | +0.88 | +0.53 | 0.20 | REJECTED | PASS ONLY WHEN SIZED DOWN | 8% |
| MRNA | H002_three_soldiers | -49% | -86% | +0.46 | +0.53 | 0.30 | REJECTED | PASS ONLY WHEN SIZED DOWN | 11% |
| MRNA | H003_monday_replication | -31% | -86% | -0.14 | +0.53 | 0.48 | REJECTED | PASS ONLY WHEN SIZED DOWN | 11% |
| MRNA | H004_trend_50_band | -61% | -86% | +0.61 | +0.53 | 0.23 | REJECTED | PASS ONLY WHEN SIZED DOWN | 8% |
| TSLA | H001_trend_ma200 | -65% | -73% | -0.26 | +0.28 | 0.92 | REJECTED | PASS ONLY WHEN SIZED DOWN | 9% |
| TSLA | H002_vol_target | -55% | -73% | +0.18 | +0.28 | 0.83 | REJECTED | PASS ONLY WHEN SIZED DOWN | 10% |
| TSLA | H003_monday_effect | -54% | -73% | +0.40 | +0.28 | 0.06 | REJECTED | PASS ONLY WHEN SIZED DOWN | 9% |
| V | H001_news_overreaction | -43% | -29% | -1.38 | +0.68 | 0.99 | REJECTED | PASS ONLY WHEN SIZED DOWN | 19% |
| V | H002_vol_target_replication | -29% | -29% | +0.64 | +0.68 | 0.65 | REJECTED | PASS ONLY WHEN SIZED DOWN | 17% |
| V | H003_fear_filter | -41% | -29% | -0.11 | +0.68 | 1.00 | REJECTED | PASS ONLY WHEN SIZED DOWN | 16% |
| V | H004_hype_fade | -34% | -29% | +0.57 | +0.68 | 0.63 | REJECTED | PASS ONLY WHEN SIZED DOWN | 15% |

## Trade strategies (per trade, account returns, out-of-sample)

| Ticker | Hypothesis | Instrument | Trades | Worst trade | Mean/trade | Random mean | p | Edge verdict | Protection | Safe size/trade | Safe ~annual |
|---|---|---|---|---|---|---|---|---|---|---|---|
| POOLED(NSIT,CNMD,SPSC,JOE,…) | T007_sc_insider_cluster_drift20 | stock_long | 112 | -10.6% | +1.48% | +0.22% | 0.10 | REJECTED | PASS ONLY WHEN SIZED DOWN | 5.4% | +1.9% |
| POOLED(SUPN,QNST,MTRN,ADAM…) | T010_sc_cluster_replication | stock_long | 230 | -13.6% | +0.19% | +0.15% | 0.47 | REJECTED | PASS ONLY WHEN SIZED DOWN | 2.5% | +0.9% |

Protection = full-history check against -2%/trade and -10% drawdown limits; returns shown at the safe size.

36 tests, 0 supported.
