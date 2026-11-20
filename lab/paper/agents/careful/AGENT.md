# Agent "careful": default, protection-first (v2 from 2026-10-21; v1 below)

**v2: trades whenever its rule fires** (user decision 2026-10-20; config.json, v1 kept in config_v1.json).
v1 ran 2026-10-19 and 2026-10-20 and made no trades, so v2 starts from the same $1,000.

- **Watches** 09:30–10:15 ET as before, then **re-checks its entry rule every minute from 10:15 to
  15:00 ET** instead of once at 10:15.
- **Entry rule (unchanged):** price above today's open, above VWAP so far and above yesterday's
  close; the forecast range still has ≥ 1% of room left (expected range minus today's high−low so
  far); forecast P(touch +1%) ≥ 35%. If several qualify, it takes the strongest above VWAP.
- **Orders:** limit buy at the last price + 0.05%, live one minute after the decision; **cancelled
  if not filled within 15 minutes** (the stock may qualify again later).
- **Limits:** at most **2 trades a day** (a filled trade keeps its slot after it exits), one per stock;
  never more than 2 live at once.
- **Risk and exits (unchanged):** stop at the higher of today's low so far and −0.75%; size so a
  stop-out loses ≤ 0.5% of the account, capped at 40% per position and 80% total; sell limit at
  **+1%**, the stop, or sell at 15:55 ET.
- **How it runs:** a minute-by-minute decision can't be made by three timers a day, so the evening
  run **replays the day minute by minute**, giving each decision only the bars that ended before that
  minute. The rule is frozen in git before the session opens. A test truncates the bars at many
  decision times and checks that no decision up to that time changes (92 checks, 0 mismatches,
  2026-10-20). One known difference from live trading: the evening uses Yahoo's final bars, whose
  volume can be revised slightly after the fact (VWAP moved by up to $1.55 on TSLA on 2026-10-20).
- **Changes:** none for the rest of the test. Afterwards, only via a new pre-registered version.

---

## v1 (2026-10-19 to 2026-10-20): watches 45 minutes, decides once (pre-registered 2026-10-16)

- **Starts with:** $1,000, simulated cash account (T+1 settlement), long only, flat every night.
- **When:** watches 09:30–10:15 ET (1-minute bars), decides between 10:15 and 11:00 ET; if it can't
  run in that window, it does not trade that day.
- **Buys only if all hold:** price above today's open, above the 45-minute VWAP (volume-weighted
  average price) and above yesterday's close; the forecast range still has ≥ 1% of room left;
  forecast P(touch +1% from the open) ≥ 35%. Takes at most 2 names, the strongest above VWAP.
- **Orders:** limit buy at the 10:15 price + 0.05% (if the price runs away, it doesn't chase).
- **Risk:** stop at the higher of the 45-minute low and −0.75%; size so a stop-out loses ≤ 0.5% of
  the account, capped at 40% per position and 80% total.
- **Exits:** sell limit at **+1%**, the stop, or sell at 15:55 ET.
- **Isolation:** same as bold: its own folder plus shared market data only; comparison locked for 7 days.
- **Changes:** none during the first 7 trading days. Afterwards, only via a new pre-registered version.

**Universe pinned, 2026-10-28 (rules unchanged):** TGT, WMT and LITE joined the forecast universe for the new
agents. This control's `universe` in config.json keeps it on its original 10 stocks, so its decisions stay
exactly as before. The test window was extended to 2026-11-13 so the controls run beside bold2 and careful3.
