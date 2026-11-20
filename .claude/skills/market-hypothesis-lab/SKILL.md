---
name: market-hypothesis-lab
description: Run a scientific hypothesis → screen → test → verdict → next-hypothesis loop on stocks using historical prices, market sentiment (VIX, credit, SKEW), insider trades (SEC EDGAR), short interest (FINRA) and news tone (GDELT). Tests either position strategies (vs buy-and-hold) or per-trade goals such as "+1% per trade" on stocks and modeled options (covered calls, cash-secured puts, spreads, long calls/puts), with honest backtests (out-of-sample split, costs, lookahead check, random-entry p-values, multiple-testing tracking), polite rate-limited data collection, and a journal of every result. Use this whenever the user wants to analyze a stock with historical data, test a trading or options idea, check whether a pattern or sentiment signal "works", backtest a signal, aim for a modest gain per trade, or iterate on trading hypotheses, even if they don't say "hypothesis" or "backtest".
---

# Market Hypothesis Lab

Turn trading ideas into falsifiable hypotheses, test each one once on data it has never
seen, record the verdict, and use what was learned to choose the next hypothesis.

The point is **feedback you can trust**. Backtests lie easily: peeking at future data,
ignoring costs, tuning until something fits, and forgetting how many ideas were tried all
make noise look like an edge. Every step below exists to stop one of those failure modes.
When a rule here feels inconvenient, remember that skipping it makes the result meaningless.

This is research, not financial advice. Never recommend trading real money on a result.

## First principle: protect capital

**Protecting the existing investment comes before any gain.** A strategy that might make
money but can lose a lot is a failure here. Every test therefore produces two verdicts:

1. **Edge verdict** (pre-registered): is the signal better than chance out-of-sample?
2. **Capital-protection verdict** (`scripts/protect.py`, always run on the full history,
   including 2008 and 2020): at the planned size, did any single trade (or day) lose more than
   **2% of the account**, or the account fall more than **10%** from a peak? It also reports
   the **safe size**: the largest position that would have stayed inside those limits,
   counting overlapping positions in pooled tests, and never committing more than 100% of
   the account at once.

A strategy is **usable** only if both pass, at the safe size. When reporting:
- lead with the downside: worst trade, drawdown, safe size;
- quote expected gains **at the safe size**, never at full size;
- prefer defined-risk structures (stops, spreads, collars) over open-ended risk;
- call out anything that can lose 100% of a position (long options, 0DTE) and size it accordingly;
- tighter limits can be set per hypothesis with `"protection": {"max_trade_loss": 0.01, "max_drawdown": 0.05}`,
  but never looser ones without the user explicitly asking.

## Two kinds of hypothesis

| | Position strategy (`H###`) | Trade strategy (`T###`) |
|---|---|---|
| Question | Does holding/sizing by this signal beat buy-and-hold? | Does entering on this signal reach a modest target per trade (default **+1%**) more reliably than random entries? |
| File defines | `signal(df)` → position in [-1, 1] | `entries(df)` → bool, plus `instrument`, `exit`, `params` |
| Instruments | the stock | stock long/short, covered call, collar, cash-secured put, put-credit spread, call-debit spread, long call/put (options are **modeled**) |
| Engine | `backtest.py` | `trade_backtest.py` |
| Judged on | OOS Sharpe/drawdown vs buy & hold, timing p-value | OOS mean account return per trade (expectancy), worst trade, win rate, p-value vs random entries |

If the user's goal is a small, steady gain per trade with capital protection, use trade
strategies. Read `references/trades_and_options.md` before writing the first one.

## Setup

One lab per ticker keeps each stock's journal and multiple-testing count separate:

```
lab/<TICKER>/
  data/        prices, market sentiment series, IRX (rates), insider / short / news files
  charts/      candlestick charts
  hypotheses/  H###_slug.py or T###_slug.py, written BEFORE testing
  results/     metrics JSON, charts, trade ledgers
  JOURNAL.md   every test ever run, pass or fail
```

Scripts are in this skill's `scripts/` folder and run with `uv run`. Always pass `--lab lab/<TICKER>`.

```bash
uv run <skill>/scripts/cache.py status                                       # what is already cached
uv run <skill>/scripts/fetch_data.py AMD --lab lab/AMD --start 2004-01-01   # prices
uv run <skill>/scripts/sentiment.py fetch --lab lab/AMD                      # VIX, VIX3M, SKEW, HYG, LQD, SPY, IRX
uv run <skill>/scripts/alt_sentiment.py finra AMD --lab lab/AMD              # short interest (fast)
uv run <skill>/scripts/alt_sentiment.py edgar AMD --lab lab/AMD --start 2015-01-01  # insider trades
uv run <skill>/scripts/alt_sentiment.py gdelt AMD --lab lab/AMD --query '"Advanced Micro Devices"'  # news
```

**Everything is cached machine-wide** (`scripts/cache.py`, default `~/.cache/market-hypothesis-lab/data`,
override with `MHL_CACHE`). A fetch:
- makes **no network request** if that item was refreshed within `--max-age` hours (default 20);
- otherwise downloads **only what is new** since the cached copy: new filings, recent news
  days and recent price bars. A first insider download for a large company takes 10–40
  minutes; an up-to-date refresh takes seconds;
- copies a `--start`/`--end` filtered view into the lab. For EDGAR, `--start` also limits
  what is downloaded the first time, which is the main lever for speed. Asking later for an
  earlier start backfills automatically.

Run `cache.py status` before fetching to see what's already there. Use `cache.py materialize
<T> --lab ... --start ...` to re-cut a lab's window without any download. Use `--refresh`
only when you really need today's data. Sources, history depth and point-in-time rules are
in `references/data_sources.md`.

If a journal already exists, read it first. The loop continues where it stopped, and the
test count matters for multiple-testing correction.

## Being gentle with data providers (mandatory)

Every network call goes through `scripts/polite.py`. It enforces per-host minimum
intervals (SEC 2/s, FINRA 1 per 2 s, GDELT 1 per 30 s, Yahoo 1 per 3 s), daily caps, and
Retry-After or exponential backoff on HTTP 429/503 and "slow down" pages, plus a circuit
breaker after 5 consecutive failures. The limits are shared across processes through a
locked state file, so parallel downloads cannot add up.

- Never write a fetcher that bypasses `polite.request()`. Wrap library calls you don't
  control (yfinance) with `polite.wait(host)` and `report_failure`/`report_success`.
- Never raise the limits above the providers' published ones. Lowering them is always fine.
- Check the cache first (`cache.py status`). Never delete it to "start fresh"; use `--refresh`.
- Run long first-time downloads (EDGAR, GDELT) in the background, one process per provider,
  and work on whatever data is ready meanwhile. Narrow EDGAR with `--start` when the
  hypothesis doesn't need older history.
- If a fetch stops with "Stopped politely" or a daily cap, tell the user and resume later.
  Do not retry in a loop.
- SEC asks for a contact in the User-Agent. Ask the user for one and set `SEC_USER_AGENT`.
  Never use unofficial broker APIs or ask for brokerage credentials.

## The loop

### 1. Observe (in-sample only)
Every exploration tool shows only the first 70% of the evaluation window. The last 30% is
the out-of-sample (OOS) period, reserved for verdicts.

- `explore.py`: return statistics, autocorrelation, calendar effects, behavior after big
  moves, trend and volatility regimes, and a candlestick-pattern table.
- `sentiment.py explore`: returns under VIX, term-structure, SKEW, credit and SPY regimes,
  attention and gaps, and, once fetched, insider buying and selling, short-interest
  crowding and covering, and news tone and volume bursts. Use `--start 2018-01-15` for the
  features that begin in 2017–18.
- `candles.py`: weekly and daily candle charts. **Open the PNGs with Read.** The chart's
  shape (steady compounder, boom-bust, bubble) is often the best guide to which idea fits.

Note 2–4 plausible patterns. With ~20 rows per table, expect about one |t|>2 by chance. A
pattern seen on several stocks, with a mechanism, is worth much more than one strong row.

### 2. Hypothesize and pre-register
Write the hypothesis file **before** any test, numbering sequentially. Position example:

```python
import pandas as pd

HYPOTHESIS = {
    "ticker": "TSLA",
    "statement": "Holding TSLA only while Close > 200-day SMA beats buy-and-hold on Sharpe.",
    "rationale": "In-sample: forward 20d returns were higher above MA200 than below.",
    "pass_criteria": {"max_p_value": 0.05, "beat_buy_hold_sharpe": True, "min_trades": 10},
    # "start": "2018-03-01",   # optional: evaluate only where the data exists
}

def signal(df: pd.DataFrame) -> pd.Series:
    return (df["Close"] > df["Close"].rolling(200).mean()).astype(float)
```

The trade-strategy template and the instrument and sizing rules are in
`references/trades_and_options.md`.

A good hypothesis is **falsifiable** (pass criteria fixed in advance), **mechanistic** (says
why it might work), and **simple** (few parameters, round numbers). Useful imports inside a
hypothesis:
- `from sentiment import features; f = features(Path(__file__).parents[1], df)` gives every
  sentiment column with publication lags already applied (list in `references/data_sources.md`).
- `from patterns import hammer` and the other candlestick detectors.

Signal and entry rules: use only `rolling`, `shift(+n)` and expanding windows. Never use
`shift(-n)`, full-sample statistics, quantiles of the whole period, or `center=True`. Both
engines recompute the signal on truncated history and mark any lookahead invalid.

### 3. Screen (free)
Run `screen.py <hypothesis> --lab ...`. It runs the exact rule on the two halves of the
in-sample period only:
- position strategies must beat buy-and-hold in both halves;
- trade strategies must make money per trade *and* beat random entries in both halves.

An edge that lives in one half is usually one episode (2008, 2020) in disguise. Screened-out
ideas are noted in the journal as "screened out" and do **not** count as tests. Stopping a
ticker because nothing passes the screen is a valid outcome.

### 4. Test once
Run `backtest.py` (position) or `trade_backtest.py` (trade). The verdict is decided on OOS
only and appended to `JOURNAL.md`. Each run is one test. Never edit a hypothesis after
seeing its result and re-run it under the same ID; a variant is a new hypothesis. Use
`--no-journal` only to debug code, never to preview results.

### 5. Interpret
After the verdict, the OOS period may be looked at:
- for position strategies, `candles.py <T> --lab ... --hypothesis <file> --start <split>`;
- for trade strategies, `results/<id>_trades.csv` and `results/<id>.png`, which show the
  equity curve and the distribution of returns per trade.

Replace the journal's `_TODO_` with 2–4 sentences: what happened and why; in-sample vs OOS;
whether a few trades or one period drove it; for trades, the win-rate trap (see below);
and what this rules out or points to.

### 6. Choose the next hypothesis
Follow the evidence: change the family after a clear failure, and try a mechanism-based
variant (not a re-tuned parameter) after a near-miss. Test the same rule on other stocks
to check that it replicates. Ideas, families and past findings are in
`references/hypothesis_ideas.md`; read its findings section so you don't repeat dead ends.

### 7. Stop and report
After the requested number of cycles (3–5 per ticker by default), summarize:
- a table of every test across tickers (`summarize.py`), showing protection verdict and safe size;
- what replicated across stocks and what didn't;
- anything that survives multiple-testing correction;
- what is still open.

## Live forward test (no trades)
Backtests answer "would it have worked"; a live test answers "does it work on days nobody has
seen". `scripts/forecast.py` predicts each stock's day **before the open** and scores it
**after the close**:
- `predict` (before 09:30 ET) writes `predictions/<date>.csv` once (never overwritten), using
  data through the previous close: σ, P(up), 68%/95% close bands, expected range, and
  P(touch ±1% from the open);
- `score` (after ~17:00 ET) compares with the day's bar and appends to `scorecard.csv` and
  `daily/<date>.md`, alongside a naive baseline;
- `report` summarizes calibration and skill vs naive; `backtest` runs the same frozen model
  walk-forward on history (do this before going live).
Forecasts made at or after 09:30 ET on their own day (e.g. a delayed scheduled run) are kept for
the record but automatically excluded from scores, `report` and `leaderboard` (`made_at` check).
GitHub's scheduled runs can be hours late: trigger time-critical steps externally (e.g. a timer
service calling the workflow_dispatch API) and keep the schedule only as a backup.
Write a `MODEL.md` with the frozen model and **pre-registered update rules** before day one.
After the period, change only what those rules allow, as a new version in `params.json`;
never rescore old days. Schedule the two runs (e.g. with the app's scheduled tasks) in the
user's local time, and keep the folder somewhere permanent.

## Paper trading with realistic execution (no real orders)
`scripts/paper.py` runs isolated agents with simulated cash (e.g. $1,000 each):
- each agent folder holds `config.json` + `AGENT.md` (pre-registered rules), `state.json` (settled and
  unsettled cash), `orders/`, `fills/`, `journal/` and `equity.csv`. `decide()` reads ONLY the agent's own
  folder plus shared market data (prices, 1-minute bars, the champion forecast);
- `decide` writes orders once, with a timestamp. Pre-open agents decide before 09:30 ET; watch-first
  agents decide inside a window (e.g. 10:15–11:00 ET) from 1-minute bars, and skip the day if they miss it;
- a `watch_then_scan` agent (careful v2) re-checks its rule every minute in a window (e.g. 10:15–15:00):
  `execute` replays the day minute by minute, giving each decision only the bars that ended before its
  minute, with a per-order random seed. Verify with `check_scan_lookahead.py` (cutting the bars at a
  decision time must leave every earlier decision unchanged) before trusting any replayed agent;
- `execute` (after the close) simulates fills on 1-minute bars under `market_rules.json`: one-minute
  latency, half-spread costs (wider at the open), random adverse slippage, limit fills only on a
  trade-through (touches fill with 30% probability), stops fill at the worse of stop/open plus
  slippage, stop assumed first when target and stop share a bar, close-out at 15:55, T+1 settlement
  in a cash account, SEC/FINRA sell fees;
- `compare` shows each agent only once it has `unlock_after_days` trading days, so reviewers can't
  judge an agent on a few lucky or unlucky days;
- `--as-of HH:MM` exists only to replay past days in tests; such journals say SIMULATED.
- An `external_calls` agent (e.g. "follower") buys the outside calls recorded before that session's
  open, at a fixed % of the account per call, using MODELED option prices (options.py) with option
  spreads (wider at the open), per-contract commission and latency; it holds overnight, values
  positions daily at the modeled bid, and exits at a profit multiple or at expiry. With small
  accounts it uses fractional contracts and says in each journal what a real account would need.
  `retired_from` in its config stops new calls while held positions run to expiry.
- agents with the same `team` in config.json (bold2 + careful3) are replayed together minute by minute
  and share timestamped notes (buys, targets, stops; readable one minute after the bar), saved in
  `<root>/notes/<date>.csv`; `open_then_scan` places pre-open orders in the morning and keeps cash for
  the day; check with `check_scan_lookahead.py --team`. A `universe` list pins an agent to fixed symbols.
- a `checkpoints` agent (season 2: careful v3, hybrid) decides LIVE at fixed times (`paper.py checkpoint` at
  e.g. 10:15/11:00/12:00/13:00/14:00 ET, on bars before that minute) and writes limit buys with fixed target
  and stop prices; `execute` simulates those exact orders (never re-decides), and `alpaca_mirror.py
  checkpoint` sends them as bracket orders, so the simulator and the broker follow identical decisions. A run
  more than `grace_min` after its checkpoint decides nothing. `<root>/exclusions.csv` keeps event-driven stocks
  (e.g. takeover targets) out of every agent in that root.
- `earnings_cal.py` (morning) lists the stocks whose earnings reaction day is today in
  `<root>/earnings/<date>.json`; `skip_earnings_reaction_open` leaves them out of an agent's opening buys
  (lab/earnings E002) and `log_earnings_reaction` adds a shadow line to the journal.
- `scripts/alpaca_mirror.py` mirrors pre-open agents' buys to dedicated Alpaca PAPER accounts (paper endpoint only,
  accounts must start with "PA"; keys only from environment secrets): market-on-open buys, broker-held OCO exits
  placed after the fills, a 15:55 close, and an evening comparison of broker vs simulated fills. Never real money.
A `spreads_at_10` agent ("spreads") buys option DEBIT spreads (defined risk: the debit is the most it can lose) at
10:00 ET on bars before 10:00, direction from the first 30 minutes, MODELED prices; exits (target, stop on the
spread's mid, time exit) are checked minute by minute in `execute`; it skips stocks with earnings before its exit day.
Judge agents on capital protection first (worst day, drawdown), then return. A few weeks of paper
results is a small sample: report it as such.

## Scoring outside calls (social media, alert services)
`scripts/external.py` records other people's option calls **before the open** with our model's odds
(P(ITM), P(touch), modeled premium, P(profit)) and scores them after expiry (in the money or not,
held-to-expiry return, hindsight best case, and the Brier score of our odds), with a per-source
summary in `lab/external/REPORT.md`. Outside calls never feed the frozen model or the paper agents.
Stock plans (long/short, optional 15m/1h/daily close trigger, stop, target) go in with `external.py plan` as P###, with our chance-alone odds (P(trigger), P(target before stop)); `score` replays them nightly on real 1-minute bars while they run (Yahoo keeps those bars about 30 days), so record a plan before its first session and keep the evening step running. Finished plans are appended to `plans_scorecard.csv`; plans still waiting or in a position are rewritten each night to `plans_live.csv` (marked to the close, with how close they came to the stop) and shown in REPORT.md as "Open plans", which are not results.
Record contracts exactly as posted and note inconsistencies (e.g. a Monday expiry on a stock that
lists Friday options) instead of guessing. Verify any market numbers in a post against data; label
claims that data can't check as unverified.

## Honesty rules
- Capital first: never present a return without its worst case and safe size.
- SUPPORTED means "worth a closer look, then paper trading", never "this makes money".
- If N tests were run at p<0.05, about N×0.05 passes are expected by chance. Point to the
  Bonferroni column.
- **Win rate is not profit.** A +1% target with a 5% stop can win 80% of trades and still
  lose money. Lead with the mean return per trade and the worst trade.
- Option results are **modeled**: Black-Scholes calibrated to Cboe's PUT index (see
  `validate_options.py`). Say so, and say that real fills, early assignment and liquidity
  in small names can be worse.
- Selling options (cash-secured puts, covered calls, credit spreads) earns small, frequent
  gains with occasional large losses. "Protection" comes only from defined-risk structures
  (spreads, collars) or stops. Be explicit about the worst case.
- Regime change is the most common reason a screened idea fails OOS. Name it when you see it.
