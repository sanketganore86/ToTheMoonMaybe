# Dip lab: buying large caps after a market sell-off day (pooled, 30 large caps)

Asked by the user on 2026-11-05, during a chip-led sell-off (SPY about -2.9%, QQQ -4.6%, VIX +56% by 11:00 ET):
"check if we should buy in dip". Backtest only: the paper agents and the forecast stay unchanged until 2026-11-13.

Data: SPY daily bars 1999 -> 2026-11-04 (`data/SPY.csv`, Yahoo, adjusted); stock bars shared with the earnings lab
(30 tickers incl. the paper agents' 13, through 2026-10-28). Events from 2002. Trades: buy at the event-day close,
sell at the close 5 sessions later, 0.045% per side (`events.py`). Split: first 70% of D001's event days in-sample,
the rest out-of-sample. p-values draw whole random days (all 30 stocks together), because stocks on the same
day move together; counting each stock as an independent trade would overstate the evidence.

## What had already been seen before pre-registration (disclosed, so the verdicts can be weighed)
Earlier the same day, a quick exploratory look (not a test; no journal entry) over 1999-2026, all years
including what is now out-of-sample:
- 18 separate episodes of SPY <= -2.5% with VIX >= +30% in one day: SPY 5 days later +0.3% mean, 72% up;
  20 days later -0.7% mean (worst -30.4%, Feb 2020); random days +0.2% / +0.8%.
  Split by trend: 12 episodes with SPY above its 200-day average, +5d 11 of 12 up (+1.4% mean);
  6 below, 2 of 6 up (-2.0%).
- QQQ <= -4%, SMH <= -7%, AMD <= -12%, TSLA <= -9% days: no clear edge at 1-60 days, large further drops
  (median further fall within 20 days -7% to -10%).
D001/D002 use a different event (SPY <= -2%, no VIX condition), a different instrument (30 stocks, pooled) and a
pre-set 5-day hold, but they overlap with those episodes. **D002's uptrend condition was chosen after seeing that
the above-200-day subset looked good**, which is exactly the kind of choice that makes noise look like an edge.
D002 therefore counts as a test and gets no benefit of the doubt: treat a D002 pass as "needs a forward test".

## Pre-registered (2026-11-05, before any screen or test)
- `hypotheses/D001_dip_buy_5d.py`: any SPY <= -2% day, vs random days.
- `hypotheses/D002_dip_buy_uptrend_5d.py`: same, only when SPY closed above its 200-day average the day before,
  vs random uptrend days.
Both: pass = OOS pooled mean > 0, above the random-day mean, p < 0.05, at least 10 event days.
Planned size for the protection check: 20% of the account per event day (equal weight across the stocks).

## Screen (in-sample halves, 2002 -> 2018-12-04): both passed
- D001: first half (87 days) +0.474%/trade vs random +0.075% (p = 0.14); second half (88 days) +1.563% vs +0.420% (p < 0.001).
- D002: first half (28 days) +0.810% vs +0.334% (p = 0.16); second half (29 days) +0.345% vs +0.269% (p = 0.43).

## D001 dip_buy_5d — REJECTED — tested 2026-11-05
OOS 2018-12-07 -> 2026-06-05: 76 sell-off days, 2,280 stock trades.
- **+0.97%/trade (5 days) vs +0.48% on random days, difference +0.49%, p = 0.078** (pass needed p < 0.05). Near miss.
- Per basket (all 30 stocks bought together): 62% of sell-off days ended up after 5 days; worst basket -19.1%
  (bought 2020-03-05), worst single stock -43.1% (TSLA).
- **Capital protection: PASS ONLY WHEN SIZED DOWN.** At the planned 20% of the account per sell-off day: worst
  trade -3.8% of the account (limit -2%), drawdown -9%. Safe size 10.5% per day: +0.11% of the account per
  trade, drawdown -5.0%, ~+1.1%/yr.
- After the verdict: 2020 dominated (24 of 76 days; the best and worst five baskets are mostly March 2020).
  Without 2020: +0.84% per basket, 60% up. 2022's 23 sell-off days lost money (-0.5%, 48% up), the bear-market
  case the earlier finding warned about. Random days earned +0.48% per 5 days in a strong 2019-26 market, so
  most of the dip "gain" is just being long in a rising market.

## D002 dip_buy_uptrend_5d — REJECTED — tested 2026-11-05
OOS 2019-05-13 -> 2026-06-05: 33 uptrend sell-off days, 990 trades.
- **+0.79%/trade vs +0.45% on random uptrend days, difference +0.34%, p = 0.23.**
- Baskets: 67% up after 5 days; worst basket -19.1% (2020-03-05: SPY was still above its 200-day average).
- Capital protection: PASS ONLY WHEN SIZED DOWN; safe size 10.5% per day: +0.07%/trade, ~+0.2%/yr.
- The trend condition that looked good in the quick SPY look (11 of 12 episodes up) did not carry over: it
  did not beat random uptrend days, and it did not avoid the worst case (Feb-Mar 2020 began in an uptrend).

## What this says about today (2026-11-05)
Buying the dip at the close of a sell-off day has been, on average, slightly better than buying on a random day,
but not reliably (p = 0.08 and 0.23), and the downside is large: 38% of OOS sell-off baskets were lower 5 days
later (worst -19%), and in the earlier SPY look 1 episode in 4 fell another 6% or more within 20 days.
It is not a rule to add to the agents. It does not say what happens today.

Tally: 2 tests (D001, D002 rejected). Project total: 42 tests, 1 supported (E002, p = 0.0002 still passes
Bonferroni at 0.05/42 = 0.0012).
