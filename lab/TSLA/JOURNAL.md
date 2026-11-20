# Hypothesis Journal

Each entry is pre-registered, tested once out-of-sample, and kept whether it passed or failed.

## H001_trend_ma200 — REJECTED
*TSLA, tested 2026-10-16T12:11:51, costs 10 bps, split 2021-11-19*

**Hypothesis:** Holding TSLA only while Close > 200-day SMA (flat otherwise) gives a higher OOS Sharpe than buy-and-hold, with timing better than chance.
**Rationale:** In-sample, forward 20d returns averaged +6.1% above MA200 vs +4.2% below; trend persistence from herding/slow information diffusion.

- In-sample  strategy: Sharpe +0.81 | CAGR +30.8% | MaxDD -73.0% | exposure 63% | trades 101
- In-sample  buy&hold: Sharpe +1.13 | CAGR +61.2% | MaxDD -60.6% | exposure 100% | trades 0
- **Out-of-sample strategy: Sharpe -0.26 | CAGR -17.3% | MaxDD -64.7% | exposure 52% | trades 67**
- Out-of-sample buy&hold: Sharpe +0.28 | CAGR -0.8% | MaxDD -73.0% | exposure 100% | trades 0
- Timing p-value (OOS, circular-shift null): 0.915  (Bonferroni alpha after 1 tests: 0.0500)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected decisively. Even in-sample the filter lost to buy&hold (Sharpe 0.81 vs 1.13) and had a *deeper* drawdown: TSLA's 56% vol whipsaws price around the MA (101 trades), so it repeatedly exits after drops and re-enters after rebounds. OOS timing was worse than random (p=0.92). Directional trend-following on a single hyper-volatile stock looks like a dead end. The one robust in-sample fact is volatility clustering (|r| autocorr +0.17 vs r autocorr ~0) → next test sizing by volatility, not direction.

## H002_vol_target — REJECTED
*TSLA, tested 2026-10-16T12:12:24, costs 10 bps, split 2021-11-19*

**Hypothesis:** Scaling the TSLA position to target 40% annualised volatility (position = 0.40 / realised 20d vol, capped at 1, long-only) beats buy-and-hold on both OOS Sharpe and OOS max drawdown.
**Rationale:** Volatility clusters strongly (|r| lag-1 autocorr +0.17) while direction does not (r autocorr ~0), so de-risking after vol spikes should cut drawdowns more than returns.

- In-sample  strategy: Sharpe +1.05 | CAGR +42.4% | MaxDD -51.3% | exposure 99% | trades 1843
- In-sample  buy&hold: Sharpe +1.13 | CAGR +61.2% | MaxDD -60.6% | exposure 100% | trades 0
- **Out-of-sample strategy: Sharpe +0.18 | CAGR -1.3% | MaxDD -55.2% | exposure 100% | trades 1054**
- Out-of-sample buy&hold: Sharpe +0.28 | CAGR -0.8% | MaxDD -73.0% | exposure 100% | trades 0
- Timing p-value (OOS, circular-shift null): 0.829  (Bonferroni alpha after 2 tests: 0.0250)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌, beat_buy_hold_drawdown=✅
- Survives multiple-testing correction: no

**Interpretation / next step:** Half right: drawdown fell from -73% to -55%, but Sharpe fell too (0.18 vs 0.28), and timing was no better than random (p=0.83). The in-sample vol-quintile table explains why: TSLA's *highest* next-day returns came in the highest-vol quintile (+0.63%/day, t=3.3), so cutting exposure in high vol sells the best days. For TSLA, volatility is the return, not just risk. Vol-scaling is a drawdown tool, not an edge. Next: the strongest raw in-sample statistic, the Monday effect (t=+3.5), mostly to test whether a high in-sample t-stat with a weak mechanism survives OOS.

## H003_monday_effect — REJECTED
*TSLA, tested 2026-10-16T12:12:43, costs 10 bps, split 2021-11-19*

**Hypothesis:** Holding TSLA only on the trading day after Friday (Monday) earns a better OOS Sharpe than buy-and-hold, with timing better than chance.
**Rationale:** In-sample Monday mean return +0.61%/day (t=+3.5) vs +0.25% overall. Possible mechanism: weekend news/announcements priced in Monday. Mechanism is weak, so this doubles as a data-mining check.

- In-sample  strategy: Sharpe +0.70 | CAGR +17.5% | MaxDD -43.3% | exposure 20% | trades 1150
- In-sample  buy&hold: Sharpe +1.13 | CAGR +61.2% | MaxDD -60.6% | exposure 100% | trades 0
- **Out-of-sample strategy: Sharpe +0.40 | CAGR +7.7% | MaxDD -54.3% | exposure 20% | trades 494**
- Out-of-sample buy&hold: Sharpe +0.28 | CAGR -0.8% | MaxDD -73.0% | exposure 100% | trades 0
- Timing p-value (OOS, circular-shift null): 0.057  (Bonferroni alpha after 3 tests: 0.0167)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=✅
- Survives multiple-testing correction: no

**Interpretation / next step:** The most interesting near-miss. OOS it beat buy&hold on Sharpe (0.40 vs 0.28) and drawdown, with only 20% exposure, but timing p=0.057 misses the pre-registered 0.05. After 3 tests the Bonferroni bar is 0.017, so it would not count even with a small nudge. Costs matter here: two trades a week cost about half the in-sample edge. Per the protocol, it stays REJECTED; loosening the threshold after seeing the result is how backtests start lying. The effect also weakened OOS (in-sample Monday t=3.5). Next: test the same idea on *different* tickers (e.g. QQQ, NVDA, COIN). A real weekend effect should appear there too; a TSLA-only artefact will not.

