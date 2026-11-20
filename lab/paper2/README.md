# Paper trading, season 2 (from 2026-11-16)

Three agents race on the **same terms**:
- the same $1,000 in the simulator (cash account, T+1);
- the same Alpaca paper setup: notional ×10 in whole shares, one paper account each;
- the same universe (13 stocks; plus SPY and QQQ from 2026-11-19), minus `exclusions.csv`;
- the same forecasts;
- the same execution rules (`market_rules.json`, unchanged from season 1).

Season 1 (lab/paper, 2026-10-19 to 2026-11-13) is frozen; its review is
`lab/paper/SEASON1_REVIEW.md`.

**Goal (owner, 2026-11-14):** find the agent to take toward real money. careful is the
safest; the race is between it and a hybrid of bold and careful that keeps bold's ambition
and careful's caution, with every fix applied. bold keeps running as the control.

**Judged on:** capital protection first (worst day, drawdown, the 2% daily rule), then
return; t-stat ≥ 2 over about 60 trading days for the go-live gate (`lab/live/PLAN.md`).

## The agents

| | bold v3 (control) | careful v3 | hybrid v1 (new) |
|---|---|---|---|
| Decides | 08:15 ET, before the open | live at 10:15, 11:00, 12:00, 13:00, 14:00 ET | live at the same checkpoints |
| Picks | top 3 by forecast σ (biggest movers) | stocks holding up: above today's open, VWAP and yesterday's close, ≥1% of forecast range left, P(touch +1%) ≥ 35%; strongest above VWAP first | careful's "holding up" test (open, VWAP, prev close), then bold's ranking: biggest σ first |
| Buys | market at the open | limit at last +0.05%, cancelled at the next checkpoint if unfilled | same as careful |
| Target / stop | ±3% from the fill | +1% / the higher of today's low and −0.75% | +3% / today's low, at least 1% and at most 3% below |
| Size | 65% of cash in 3 equal slices | stop-out loses ≤0.5% of the account; ≤40% per stock, ≤80% total | stop-out loses ≤0.66% of the account; ≤34% per stock, up to 100% |
| Trades a day | 3 at the open | at most 2 filled | at most 3 filled |
| Worst day if every stop hits | ≈1.95% | ≈1.0% | ≈2.0% |
| Always | flat by 15:55 ET; skips `exclusions.csv` | same | same |

## Fixes applied from season 1

1. careful3's 09:45 start is dropped: careful starts at 10:15, as v2 did.
2. bold2's all-day 09:45 slot is dropped: it caused nearly all of bold2's loss.
3. bold is sized so a day where every stop hits loses at most 2% (65% invested, not 100%).
4. `exclusions.csv` keeps takeover targets and event-driven stocks out (LITE: reported MRVL
   deal). bold also keeps the E002 earnings-reaction-day skip at the open.
5. The broker report compares Alpaca's opening fills with the real opening price
   (`broker/REPORT.md`, "vs open" columns).

Rules are fixed for the season. A change is a new version that starts its own record.

### Changes during the season

| Date | Change | Why | Expected effect (replay, Nov 2–18) |
|---|---|---|---|
| 2026-11-19 | SPY and QQQ added to the universe (all agents, same day) | owner's request: track and trade the two index ETFs | bold: none (they rank 8th and 14th of 15 by forecast σ; bold buys the top 3). careful: none. hybrid: 2 QQQ trades in 13 days (−$3.60; return −4.61% → −4.78%). |

Agent rules are unchanged; only the list of stocks they may choose from grew. Results before and after the
date are reported together, since every agent got the change on the same day.

## How it runs (GitHub Actions; ET)

| Time | Step | What |
|---|---|---|
| 08:15 | morning | forecasts; bold's orders; Alpaca: bold's market buys queued, leftovers sold |
| 09:30 | broker_exits | Alpaca: bold's exit pairs after its opening fills |
| 10:15, 11:00, 12:00, 13:00, 14:00 | checkpoint | careful and hybrid decide on bars before that minute; Alpaca: earlier unfilled orders cancelled, new ones sent as bracket orders (limit buy + target + stop at the agent's own prices) |
| 15:52 | broker_close | Alpaca: cancel everything, sell everything, verify flat at 15:55 |
| 16:45 | evening | simulate the day's fills, compare agents, record Alpaca fills against the simulation |

- **Late checkpoint runs:** a run more than 20 minutes after its checkpoint decides nothing,
  and the journal lists that checkpoint as missed.
- **What the simulator replays:** the live decisions exactly as written, never re-decided.

## Alpaca accounts

| Agent | Secret prefix | Account |
|---|---|---|
| bold | `ALPACA_BOLD` | season 1's bold account |
| hybrid | `ALPACA_BOLD2` | season 1's bold2 account, reused |
| careful | `ALPACA_CAREFUL` | a new **paper** account |

The mirror refuses any account that isn't a paper account.
