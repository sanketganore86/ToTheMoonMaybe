# Hypothesis families and findings

Read "Findings so far" first so you don't repeat dead ends.

Use this when choosing the next idea, especially after a family has been ruled out.
Each entry gives a mechanism, which is the reason the idea might work. Test the plain
version first.

## Trend / momentum
- **Time-series momentum:** long when the trailing 3/6/12-month return is > 0. Mechanism: slow
  information diffusion and herding.
- **MA filter:** long above the 50 or 200-day SMA. Often fails on Sharpe but cuts drawdown.
- **Breakout:** long on a new 50-day high, exit on a 20-day low (Donchian).

## Mean reversion
- **Short-term reversal:** buy after a large down day (r < −2σ), hold 1–5 days. Mechanism:
  liquidity provision and overreaction.
- **RSI(2) extremes:** long when RSI(2) < 10, exit when > 50.
- **Gap fade:** fade large overnight gaps (needs Open; signal at open is not supported by the
  close-to-close engine, so approximate or skip).

## Volatility / risk
- **Volatility targeting:** position = target_vol / realized_vol(20d), capped at 1. Mechanism:
  volatility clusters while returns don't scale with it. Judge it on Sharpe or drawdown.
- **High-vol avoidance:** go flat when 20d vol is in the top in-sample quintile. Use a fixed
  threshold taken from in-sample data or an expanding quantile, never a full-sample one.

## Calendar / seasonality
- **Day-of-week or turn-of-month effects.** These have weak mechanisms and need many trades.
  Be skeptical: they are the classic data-mining result.

## Volume / participation
- **Volume-confirmed moves:** a big move on volume > 2× its 20d average continues; on low
  volume it reverts.

## Relative / cross-asset (needs extra data via fetch_data.py)
- Long TSLA only when QQQ is above its 200d MA (market regime filter).
- TSLA lag vs QQQ: does TSLA catch up after it under-performs the index?

## Findings so far: price-based (TSLA, GOOGL, AMD, MRNA; 2026 data)
- Plain MA200 trend filters whipsaw on high-vol single stocks. A ±3–5% hysteresis band cut
  trades by ~70% and helped, but never produced significant timing skill.
- Trend and risk filters reliably cut drawdowns by 10–25 points, yet p-values of 0.2–0.4
  show this mostly comes from lower exposure.
- Dip-buying without a trend condition buys all the way through bear markets.
- Market-wide dips (lab/dip, 2026-11-05): buying 30 large caps at the close of a SPY <= -2% day for 5 days beat
  random days by +0.49%/trade OOS 2019-26 but p = 0.08 (D001); adding an uptrend filter did not help (D002, p = 0.23).
  2020 dominated; 2022's dips lost. Safe size only ~10% of the account per dip day.
- Classic candlestick patterns showed no reliable next-day or 5-day edge (1 of 30 |t|>2,
  which then failed OOS). Several pointed the opposite way to textbook meaning.
- Day-of-week effects did not replicate across stocks.
- Vol-targeting depends on the stock: it hurts where the highest-vol periods carry the best
  returns (TSLA) and helps where they don't (GOOGL). Check the vol-quintile table first.
- A strategy that trades once or twice OOS cannot be judged, however good it looks.

## Findings so far: market sentiment (AXP, V, CAT, AAOI, ASTS; 2008–2026 data)
- News overreaction (fade big gaps and high-volume up days) worked 2008-21 and *reversed*
  after 2021 on all 4 stocks tested: news moves continued instead. Costs of ~20 bps per
  event also eat most of a +0.3% per-event edge.
- Fear filters (step aside after VIX z>1) exit at panic lows, because VIX peaks after the
  drop, and miss V-shaped rebounds. They worked in the GFC era and failed badly in 2021-26 (p≈1).
- "Buy the fear" in speculative small caps (AAOI, ASTS) and "avoid complacency" did not
  survive either.
- A low SKEW level looked predictive only with full-period quantiles (a time trend in disguise);
  with rolling percentiles the effect was gone.
- Vol targeting replicated 0 of 3 after the GOOGL near-miss. Risk reduction is real; the
  timing alpha is not.
- Ideas still open: news *momentum* post-2021 (seen only in OOS, so it needs fresh data or
  paper trading to test honestly), and sentiment from real news/social data if a source
  becomes available.

## Findings so far: insider / short / news data (in progress)
- Insider open-market buying (EDGAR): rare in large caps (2–45 buy days per stock over
  10–20 years; 176 across 9 stocks). Pooled across all 9, four variants all failed the
  split-half screen: +1% target (stock or modeled put), a 20-day drift hold, and cluster
  buys. Cluster buys did worse than random, because in large caps they occur in crises and
  the stock keeps falling. The documented effect lives in small caps; test it there with a
  broad universe rather than adding variants on a few names.
- Short interest (FINRA, 2018+) showed no consistent sign across 9 stocks in-sample. Squeeze
  dynamics on ASTS, shorts proven right on AAOI. Probably stock-specific noise.
- News tone (GDELT): unusually negative news came before bounces on AXP in-sample (n=23
  days, likely clustered in March 2020). Use the split-half screen.
- Total so far: 34 position tests on 9 stocks, 0 passed; 4 pooled insider trade ideas screened out. Every price and market-sentiment
  timing rule either failed out-of-sample or matched random timing at the same exposure.

- **Small-cap insider clusters: promising, then failed replication.** Universe A (61 random
  S&P 600 names): +1.48%/trade OOS vs +0.22% random (p=0.10). Universe B (132 disjoint
  names, identical pre-registered rule): +0.19% vs +0.15% (p=0.47). This is a textbook
  example of why replication on fresh names matters: a pooled result from ~60 stocks can
  be carried by a few names. At the capital-protected size (~2.5–5% per trade) the
  expected gain is ~1–2%/yr, below T-bills.
- **Capital protection reshapes everything:** across all 36 tests, no strategy was safe at
  full size. Safe exposures were 4–27% of the account, i.e. most capital stays in T-bills.
  Compare any strategy's safe-size return with the risk-free T-bill rate (^IRX).
- **Judging outside "bots" or alert services:** see the checklist in trades_and_options.md.

## Findings so far: intraday open-to-close rules (paper agent "bold", lab/bold, 2005–2026)
- Buying the most volatile names at the open with a symmetric +/-3% bracket loses ~0.2–0.3% per trade:
  their open->close drift is ~0 and opening costs (~0.2% round trip) dominate. No regime makes it positive.
- B001 (skip days after a stressed close: VIX/VIX3M >= 0.95 or VIX >= 10% above its 20d mean) passed the
  in-sample screen but was REJECTED out of sample (p=0.14): sentiment filters reduce losses of a no-edge
  rule, they don't create an edge. Check a rule's unfiltered expectancy before adding filters.
- One-day stories don't generalize: after the 2026-10-22 semis gap-down, defensives were the day's winners,
  but historically defensives bought at the open on SPY gap-down days did worse (-0.19% open->close, t=-3.2).

## Trade-strategy families (per-trade goal, e.g. +1%)
- **Premium selling after a supportive signal:** a cash-secured put or put-credit spread
  after insider buying, after a fear spike in quality names, or in uptrends. Mechanism: the
  variance risk premium plus a lower chance of a big drop.
- **Covered calls / collars on held stock:** sell 0.20–0.30 delta calls monthly. Collars
  bound the worst trade, which suits capital protection.
- **Mean-reversion stock trades:** buy after a −2σ day in an uptrend, +1% target, tight
  time stop. Test the stop width as its own hypothesis.
- **Long options on rare strong signals:** debit spreads or calls after insider clusters.
  Use a small allocation (2–10% of the account).
- Always compare against the random-entry baseline. Premium selling makes money on random
  days in calm markets, so the signal has to add to that, not just ride it.

## Common pitfalls checklist
- Full-sample statistics in the signal: lookahead.
- Parameters picked by scanning many values: overfitting. If you scan, every value counts as a test.
- Results driven by 2020 alone: check the chart; TSLA had extreme regimes.
- Shorting TSLA ignores borrow costs and squeeze risk; prefer long/flat unless the claim is about shorting.
- Too few trades (< 10 OOS): no statistical power. Treat the result as inconclusive, not as a pass.

### Earnings reaction days (lab/earnings, 2026-10-28)
- E002 SUPPORTED (pooled 30 large caps, OOS 2020-2026): buying at the open on an earnings reaction day and
  selling at the close returns -0.54%/trade vs -0.13% on ordinary days (p = 0.0002), after gaps up or down.
  Use it as a filter (skip), not a signal. E001 (buy gap-ups >= 5%) worked only 2012-2020: screened out.
- Open: does it hold for entries after 10:00 (needs intraday bars), and is SHORTING the reaction-day open
  (gap fade) worth a separate, pre-registered test?
