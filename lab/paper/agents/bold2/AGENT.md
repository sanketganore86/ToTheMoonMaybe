# Agent "bold2": bold, 30% more aggressive, trades all day, shares notes with careful3 (v2, from 2026-10-28)

User decision 2026-10-27. bold (v1) keeps running unchanged as the control; bold2 has its own $1,000.
Goal unchanged from bold: an aggressive risk taker.

- **Universe:** the forecast universe, 13 stocks (adds TGT, WMT and LITE to bold's 10).
- **At the open (decided before 09:30 ET from the morning forecast only):** buys the **top 2 by forecast
  volatility** (σ) with market orders at the open, each **one third** of settled cash.
- **During the day, 09:45–15:30 ET, every minute:** the last third looks for the stock with the biggest
  move since today's open that is also above yesterday's close; limit buy at the last price + 0.05%,
  cancelled after 15 minutes if not filled. At most 3 positions at once, one fill per stock per day.
- **Exits:** target **+3.9%**, stop **−3.9%** (bold's ±3% × 1.3), otherwise sell at 15:55 ET.
- **Shared notes with careful3:** it skips a stock either agent was stopped out of in the last 60 minutes,
  and a stock careful3's view shows below VWAP (bars before the previous minute). Notes become readable one
  minute after the bar they describe; all notes are saved in `lab/paper/notes/<date>.csv`.
- **Cash:** simulated cash account, T+1 settlement. Money from a sale cannot buy again the same day, so the
  intraday third is in practice one trade a day (or more only if earlier orders went unfilled).
- **How it runs:** opening orders are placed live at 08:15 ET; the intraday decisions are replayed in the
  evening run minute by minute on the bars before each minute, together with careful3. Lookahead check:
  `check_scan_lookahead.py --team` (538 checks, 0 mismatches on 2026-10-20 to 2026-10-27, incl. loosened rules).
- **Risk profile:** a stop-out costs about 1.3% of the account per position; three at once about 3.9%,
  more if prices gap through stops. Expected to fail the capital-protection limit, by design.
- **Replay before going live (2026-10-20 to 2026-10-27, 10 stocks, in-sample, NOT evidence):** +0.04%,
  max drawdown −2.96% (bold v1 over the same days: +2.40%). MRNA was a top-2 pick every day and hit its
  stop on 4 of 6 days.
- **Runs:** 2026-10-28 to 2026-11-13. Changes only via a new pre-registered version.

**Known issue, fixed 2026-10-28:** GitHub's delayed backup timer re-ran the 2026-10-27 evening step at
20:45 ET, after this agent had been added, and simulated a 2026-10-27 day before its 2026-10-28 start
(bold2 +$10.71, careful3 +$5.54). That day was removed and the account reset to $1,000; the code now skips
any day before an agent's `start`. bold2's 2026-10-28 opening orders had already been placed live from the
$1,010.71 balance (2 × $336.90 instead of 2 × $333.33); they stand as placed, and its intraday third that day
is $326.20.

**Rule added 2026-10-29 (user decision 2026-10-28; v2.1):** bold2's **opening buys skip any stock on its
earnings reaction day** (the session after an after-close report, or the day of a before-open report). The
next-ranked stock is bought instead. Evidence: `lab/earnings` hypothesis E002, SUPPORTED out-of-sample
2020-04-30 -> 2026-10-27: buying at the open on a reaction day returned -0.54%/trade vs -0.13% on ordinary
days (p = 0.0002; 777 events, 30 large caps). The 08:15 run writes `lab/paper/earnings/<date>.json`
(`earnings_cal.py`, Yahoo report dates); if it is missing, bold2 trades without the skip and says so. The
intraday slot is unchanged (the test covered buys at the open only).
