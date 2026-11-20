# Agent "follower": trades outside calls (pre-registered 2026-10-18, v1; RETIRED from 2026-10-21)

**Retired 2026-10-21** (user decision 2026-10-20): it takes **no new calls**. The sources rarely post
checkable calls (exact contract, entry, expiry) before the open, and reading X posts automatically
needs X's paid API (scraping X breaks its terms). The 4 calls it already holds (C001–C004) run to
expiry on 10/23 and 10/26 under the rules below, so their result is still measured; after that it
holds cash. The calls are also scored separately in lab/external/REPORT.md.

- **Starts with:** $1,000, simulated cash account (T+1 settlement).
- **What:** buys every outside option call recorded in `lab/external/calls.csv` **before that
  session's open** (social media, alert services), exactly as posted: same stock, strike, call/put
  and expiry. Never re-buys a call it already took.
- **When:** decides before 09:30 ET; orders are filled one minute after the open.
- **Size:** **2% of the account per call** (capital protection). At this size, a real $1,000
  account usually cannot buy even one contract (1 contract = 100 shares). The follower therefore
  holds **fractional contracts**, the one deliberately unrealistic setting, so call quality can still
  be measured per dollar. Each journal entry says what a real account would have needed.
- **Prices:** MODELED with options.py (Black-Scholes, implied vol from realized vol, skew), validated
  against Cboe's PUT index; no real option quotes. Costs: half-spread of 4% of the option price
  (min $0.02, 2x wider in the first 5 minutes), $0.65 commission per contract (prorated), latency.
- **Exits:** sell at 15:55 ET on the expiry day (≈ intrinsic value), or earlier at the 15:55 check
  on any day the option's bid is worth **≥ 2× the entry price** (+100%). Positions are held overnight
  and valued daily at the modeled bid.
- **Isolation:** reads only its own folder, shared market data and the external-calls list.
  It never sees the other agents' orders, fills or journals; the comparison unlocks after 7 trading days.
- **Changes:** none during the test. Afterwards, only via a new pre-registered version.
