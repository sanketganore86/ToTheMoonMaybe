# Agent "spreads" (v1): defined-risk option debit spreads

Pre-registered 2026-11-05, before its first day (2026-11-09). Asked by the user ("let's enable the options as well";
chose a new paper agent now, defined-risk spreads). Simulated $1,000; **option prices are MODELED** (Black-Scholes
with the options.py volatility model; a spread is one limit order paying one leg's half-spread, 4% of that leg's
premium, doubled in the first 5 minutes; $0.65 per contract per leg), never real quotes. No tested edge: this agent is a live experiment, not a result. Days to 2026-11-13: 5,
far too few to judge it.

## Rules (fixed)
- Universe: bold2's 13 stocks without LITE (target of a reported all-stock deal; trades as leveraged MRVL).
- **10:00 ET**, using only 1-minute bars before 10:00: go down the list by forecast sigma (largest first). Skip a
  stock that is on its earnings reaction day, has a report on or before the planned exit day, whose earnings
  lookup failed, or that is already held. No earnings calendar for the day = no new spreads.
- Direction from the first 30 minutes: last price above BOTH the open and yesterday's close -> **call debit
  spread**; below BOTH -> **put debit spread**; mixed -> skip.
- Strikes from the 09:59 price: long leg at the money, short leg 5% further out (calls above, puts below), on the
  listed-strike grid. Expiry: Friday of next week (7-11 days).
- Size: the debit paid = **1% of equity** per spread (that is the maximum loss). At most 2 new spreads a day and 3
  open at once, so at most ~3% of the account is ever at risk. Fractional spreads, like the follower; each journal
  says what one real spread would cost.
- Order goes in at 10:01 (1-minute latency), paying the modeled ask.
- Exits, checked every minute: **target** a resting limit at +50% of the debit; **stop** at -50% of the debit
  when the spread's modeled MID falls to half the debit paid (checked first, at the bar's worst price), then
  sold at the bid (gaps fill worse); costs alone never trigger it; **time exit** at 15:55 on the earliest of 5 trading
  days after entry, the day before expiry, and 2026-11-13 (end of the test). Never held into expiry.
- Cash: debits use settled cash; sale proceeds settle T+1.

## Known weaknesses (said in advance)
- The model's premiums ran ~12% below a real fill (the user's TGT put); after a VIX spike real spreads can cost
  more than modeled. A debit spread's two legs offset part of that error.
- The direction rule (first-30-minute momentum) is untested; bold2's similar intraday rule has not shown an edge.
- Not mirrored to Alpaca: Alpaca rejects OCO/bracket exits on options, so exits would need a live loop.
