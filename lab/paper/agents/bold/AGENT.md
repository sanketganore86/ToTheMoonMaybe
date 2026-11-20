# Agent "bold": high risk taker, trades at the open (pre-registered 2026-10-16, v1)

- **Starts with:** $1,000, simulated cash account (T+1 settlement), long only, flat every night.
- **When:** decides before 09:30 ET from the morning forecast only (no market data from today yet).
- **What:** buys the **3 stocks with the largest forecast volatility** (σ), splitting 100% of settled
  cash equally, with **market orders at the open** (the most expensive moment: spreads are 3× wider).
- **Exits:** sell limit at **+3%**, stop at **−3%**, otherwise sell at 15:55 ET.
- **Risk profile:** fully invested in the most volatile names. Typical worst day about −3% of the
  account; gaps through stops can be worse. Expected to fail the capital-protection limit, by design.
- **Isolation:** reads only its own folder and shared market data. No access to the other agent's
  orders, fills or journal; the comparison stays locked until both have 7 trading days.
- **Changes:** none during the first 7 trading days. Afterwards, only via a new pre-registered version.

**Known issue, fixed 2026-10-21 (rules unchanged):** order sizes were rounded to the *nearest* cent, so
three equal orders could add up to 1 cent more than the settled cash. On 2026-10-21 that rejected the
TSLA order (3 × $333.92 = $1,001.76 against $1,001.75). Sizes are now rounded down. The recorded day
stays as it happened; a replay with the fix gave TSLA +$3.17 (day +$14.25 instead of +$11.08).

**Universe pinned, 2026-10-28 (rules unchanged):** TGT, WMT and LITE joined the forecast universe for the new
agents. This control's `universe` in config.json keeps it on its original 10 stocks, so its decisions stay
exactly as before. The test window was extended to 2026-11-13 so the controls run beside bold2 and careful3.
