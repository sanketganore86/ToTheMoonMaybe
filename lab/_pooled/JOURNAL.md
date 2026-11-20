# Hypothesis Journal (pooled across tickers)

Each entry is pre-registered, tested once out-of-sample, and kept whether it passed or failed. Screened-out ideas are listed but do not count as tests.

## Screened out (not tests): T001_insider_buy_stock, T002_insider_buy_csp
*Pooled over TSLA, GOOGL (Alphabet filings from 2015-10 only), AMD, MRNA, AXP, V, CAT, AAOI, ASTS; 176 insider-buy filing days in total.*

- T001 (stock, +1% / -5% / 20 sessions after a new insider open-market buy): half 1: 42 trades, win 83%, mean -0.11% (random -0.37%); half 2: 27 trades, win 78%, mean -0.50% (random -0.23%). Loses money in both halves despite high win rates (the win-rate trap).
- T002 (30d 0.25-delta cash-secured put, same exits, MODELED): half 1 mean -0.41% vs random -0.27%; half 2 +0.08% vs random -0.15%. Inconsistent, negative in half 1.
- Reading: the +1% target exits within 1-2 sessions, but the documented insider effect is a drift over weeks. The next variants test the mechanism directly (hold 20 sessions; cluster buys only).

## Screened out (not tests): T003_insider_buy_drift20, T004_insider_cluster_drift20
*Same universe. Screen baseline stabilized (each ticker's average random trade, weighted by its trade count) and T001/T002 re-screened with it; numbers above are the stabilized ones.*

- T003 (any insider buy, hold 20 sessions, stop -10%): half 1 +2.04% vs random +1.68% (better); half 2 +0.51% vs random +1.89% (worse).
- T004 (cluster: 2nd+ insider within 90 days, hold 20): half 1 -2.96% vs random +1.14%; half 2 -5.23% vs random +3.03%. Worse than random in both halves. In these mostly large-cap names, cluster buying happened in crises (insiders bought early; the stock kept falling).
- **Conclusion:** across 9 stocks and 176 insider-buy days, insider buying showed no stable edge, at a +1% target or as a 20-day drift. Large caps rarely see discretionary insider buying, and the academic effect is concentrated in small caps. A fair test needs a broad small-cap universe (dozens to hundreds of names, i.e. hours of polite EDGAR downloads), not more variants on these 9.

