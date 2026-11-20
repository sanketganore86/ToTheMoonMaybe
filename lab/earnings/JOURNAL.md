# Earnings lab: what happens on the first session after a report (pooled, 30 large caps)

Data: Yahoo earnings dates with report times (2002 -> 2026-10-27; 2,579 reaction days, 30 tickers incl. MSFT
and the paper agents' 13) and daily bars. Reaction day = next session for reports at/after 12:00 ET, same
session for reports before 09:30 ET (time stamps checked: JPM/KO/XOM/WMT/TGT/CAT ~06:00-08:00, MSFT/NVDA 16:00).
Trades: long at the open, out at the close, bold's daily-bar costs (`events.py`). Split: first 70% of events
(to 2020-04-29) in-sample, the rest (2020-04-30 -> 2026-10-27) out-of-sample. Asked by the user on 2026-10-28,
the evening MSFT reported FY27 Q1.

## In-sample exploration (explore.py)
Reaction days -0.258%/trade vs ordinary days -0.147% (n = 1,802 vs 120,631). No bucket made money: by gap size,
gap in sigmas, EPS surprise, or surprise x gap direction. Best: gap > +5% at +0.19% (t = 0.85).

## E001 big_gap_continuation — SCREENED OUT (not a test)
Buy at the open after an earnings gap >= +5%. First in-sample half (2002-2012) -0.147% (= ordinary days),
second half (2012-2020) +0.467%. Lives in one period only.

## E002 skip_reaction_day — SUPPORTED — tested 2026-10-28
Pre-registered: `hypotheses/E002_skip_reaction_day.py`. Screen: worse than ordinary days in both halves
(-0.167% p=0.011; -0.056% p=0.135).
- OOS (777 reaction days): **-0.543%/trade vs -0.132% on ordinary days, difference -0.41%, p = 0.0002**
  (5,000 random draws of ordinary days, same count per ticker). Win rate 39%; worst trade -12.9%.
- Survives Bonferroni across all 39 tests in this project (0.05/39 = 0.0013).
- Robustness (looked at after the verdict): negative in 6 of 7 OOS years (2026 so far +0.07%); 23 of 30
  tickers negative; without the 3 worst (TSLA, LITE, MU) -0.39%; gap up -0.54%, gap down -0.54%;
  with bold2's +-3.9% bracket -0.66%; MSFT's 26 OOS reaction days -0.93%.
- Interpretation: the report is priced in at the open; what remains is a wide opening spread and a large,
  directionless intraday range, and since 2020 a tendency to give back part of the gap either way
  (raw open-to-close drift -0.36% before costs). It is a **protection rule, not a profit rule**: it says when
  NOT to buy at the open. It does not say shorting works (untested), nor anything about entries later in the
  day (daily bars can't show that).
- Capital protection: skipping removes trades; it cannot add risk.

## E003 capex_profit — REJECTED — tested 2026-10-28
The user's observation on the evening MSFT reported (capex $39.4B vs ~$50B expected, EPS beat, +4% after hours):
"if capex is more, the stock falls; if capex is less and profit is more, it jumps". Pre-registered in
`hypotheses/E003_capex_profit.py` (commit 6bc62ea) before any capex data was downloaded. Capex: SEC XBRL
companyfacts (`fetch_capex.py`, de-cumulated to quarters; MSFT's 2026-09 quarter = $39.37B, matching the release).
Expected capex = trend proxy (previous quarter x (1 + mean QoQ growth of the 4 before)).
- MSFT, GOOGL, AMZN, META, reports 2023-01 -> 2026-10-27: 61 events; A (capex below trend + EPS beat) 27,
  B (capex above trend) 29, neither 5.
- **A: mean gap +1.87% (52% up). B: mean gap +1.77% (only 41% down). Difference +0.10%, p = 0.48.**
- Interpretation: on this record, capex above its trend did not lead to drops: the market rewarded higher
  spending as often as it punished it (META 2024-02 +16%, AMZN 2026-07 +13%, GOOGL 2023-07 +6%). The rule fits
  MSFT's two most memorable recent drops (2026-01 -8.7%, capex +44% above trend; 2025-10 -2.0%), which is
  probably why it feels right. Biggest weakness: the trend is not what analysts expected; with consensus capex
  estimates (not free) the answer could differ. Guidance on the call and the reported beat size also move the stock.
- Even if true, a flat-overnight agent can't use it (the move is the overnight gap).

Tally: 2 tests (E002 supported, E003 rejected); E001 screened out. Project total: 40 tests, 1 supported
(E002's p = 0.0002 still passes Bonferroni at 0.05/40 = 0.00125).
