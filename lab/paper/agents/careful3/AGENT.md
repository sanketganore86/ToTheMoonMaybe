# Agent "careful3": careful, trades all day, shares notes with bold2 (v3, from 2026-10-28)

User decision 2026-10-27. careful (v2) keeps running unchanged as the control; careful3 has its own $1,000.
Goal unchanged: **protect the capital first**; about +1% per trade is secondary.

- **Universe:** the forecast universe, 13 stocks (adds TGT, WMT and LITE to careful's 10).
- **When:** re-checks its rule **every minute 09:45–15:30 ET** (careful v2: 10:15–15:00), needing at least
  15 one-minute bars of the day.
- **Entry rule (same as careful v2):** above today's open, above VWAP so far and above yesterday's close;
  ≥ 1% of forecast range left; forecast P(touch +1%) ≥ 35%; strongest above VWAP first. Limit buy at the
  last price + 0.05%, cancelled after 15 minutes.
- **Risk and exits (same as careful v2):** stop at the higher of today's low so far and −0.75%; size so a
  stop-out loses ≤ 0.5% of the account, capped at 40% per position and 80% of the account per day; sell
  limit at +1%, the stop, or sell at 15:55 ET.
- **Slots:** at most 2 positions at once; unlike v2, a slot frees when its position exits. One fill per stock
  per day. Cash spent stays spent until it settles (T+1), so in practice it is still about 2 trades a day.
- **Shared notes with bold2:** skips a stock either agent was stopped out of in the last 60 minutes (notes
  readable one minute after the bar they describe; saved in `lab/paper/notes/<date>.csv`). It does not
  copy bold2's buys.
- **How it runs:** replayed in the evening run minute by minute on the bars before each minute, together
  with bold2 (lookahead check `check_scan_lookahead.py --team`: 0 mismatches).
- **Replay before going live (2026-10-20 to 2026-10-27, 10 stocks, in-sample, NOT evidence):** −0.59%,
  max drawdown −1.10% (careful v2 over the same days: +1.22%, no drawdown). Its 09:45–10:00 entries were
  stopped out within about 10 minutes on 2026-10-23 and 2026-10-26. The user chose to test 09:45 live anyway.
- **Runs:** 2026-10-28 to 2026-11-13. Changes only via a new pre-registered version.

**Known issue, fixed 2026-10-28:** GitHub's delayed backup timer re-ran the 2026-10-27 evening step at
20:45 ET, after this agent had been added, and simulated a 2026-10-27 day before its 2026-10-28 start
(bold2 +$10.71, careful3 +$5.54). That day was removed and the account reset to $1,000; the code now skips
any day before an agent's `start`. bold2's 2026-10-28 opening orders had already been placed live from the
$1,010.71 balance (2 × $336.90 instead of 2 × $333.33); they stand as placed, and its intraday third that day
is $326.20.

**Shadow log from 2026-10-29 (no effect on trades):** each journal says whether careful3 traded a stock on its
earnings reaction day and how that trade did, to see whether the E002 finding (bad days to buy at the open)
also holds for careful's later, confirmed entries before any rule is considered.
