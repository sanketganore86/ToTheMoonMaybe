# Hypothesis Journal

Each entry is pre-registered, tested once out-of-sample, and kept whether it passed or failed.

## H001_avoid_complacency — REJECTED
*ASTS, tested 2026-10-16T13:42:36, costs 10 bps, split 2025-02-19*

**Hypothesis:** Holding ASTS only when the VIX term structure is NOT complacent (VIX/VIX3M >= 0.85) beats buy-and-hold OOS Sharpe with timing better than chance.
**Rationale:** Speculative stocks lagged during market complacency in-sample: ASTS fwd-20d -4.84% when VIX/VIX3M < 0.85 vs +8.76% on all days; the same held for AAOI (-0.98% vs +0.76%). Mechanism: complacent markets precede risk-off rotations that hit high-beta speculative names hardest, while fear periods precede sharp rebounds.

- In-sample  strategy: Sharpe +0.90 | CAGR +56.6% | MaxDD -75.4% | exposure 72% | position changes 106
- In-sample  buy&hold: Sharpe +0.73 | CAGR +28.3% | MaxDD -85.6% | exposure 100% | position changes 0
- **Out-of-sample strategy: Sharpe +0.26 | CAGR -10.6% | MaxDD -65.8% | exposure 67% | position changes 80**
- Out-of-sample buy&hold: Sharpe +0.67 | CAGR +18.0% | MaxDD -69.4% | exposure 100% | position changes 0
- Timing p-value (OOS, circular-shift null): 0.726  (Bonferroni alpha after 1 tests: 0.0500)
- Checks: no_lookahead=✅, p_value=❌, min_trades=✅, beat_buy_hold_sharpe=❌
- Survives multiple-testing correction: no

**Interpretation / next step:** Rejected (Sharpe 0.26 vs 0.67, p=0.73); in-sample Sharpe 0.90 collapsed OOS. Stopping ASTS here: with only ~4 years of history, no remaining idea had in-sample support (hype-fade 0.77 vs 0.73, buy-fear 0.83 vs 0.73 are within noise).

