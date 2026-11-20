# Live forward test: model v1 (frozen 2026-10-16, before any live data; scoring and version rules added 2026-10-16, still before any live data)

**Purpose:** predict each stock's trading day before the open, compare with the actual
day after the close, for 10 sessions (Mon 2026-10-19 → Fri 2026-10-30). **No trades.**
Then analyze and update the model using only the rules below.

## Stocks (one per sector)
GOOGL (Communication), AMD (Technology), TSLA (Consumer Discretionary), MRNA (Health Care),
AXP (Financials), CAT (Industrials), XOM (Energy), KO (Consumer Staples), NEE (Utilities),
PLD (Real Estate).

## Schedule (Pacific time; US market 06:30–13:00 PT)
- 06:00 PT weekdays: `forecast.py predict`. Uses data through the previous close only.
  Forecasts are written once and never overwritten.
- 14:15 PT weekdays: `forecast.py score`. Compares with the day's actual bar and appends to
  `scorecard.csv` and `daily/<date>.md`.
- After the 10th session: `forecast.py report` and the review below.

## What is predicted (per stock, per day)
| Forecast | Method (model v1) |
|---|---|
| Volatility σ | EWMA, λ = 0.94, of daily log returns |
| P(close > previous close) | 252-day up-day rate, shrunk halfway to 50%. **Not a timing signal**: 36 lab tests found none, so the model does not claim one |
| 68% / 95% close bands | empirical quantiles of standardized returns (last 500 days) × σ: captures fat tails |
| Expected high–low range | median historical range/σ ratio × σ |
| P(touch +1% from the open), P(touch −1%) | historical frequency in σ-normalized units (last 500 days) |

Scored against a **naive baseline**: 20-day standard deviation, normal bands, 50% direction,
normal-theory touch probabilities.

## Validity
A day's forecasts count only if they were made **before 09:30 ET** that day (`made_at`). Late
forecasts (e.g. a delayed scheduled run) are kept for the record but automatically excluded from
all scores, the report and the leaderboard (rule added 2026-10-19 after GitHub delayed day 1's run
by 6½ hours; it removes data, it never changes how valid days are scored).

## Scores (per stock-day)
- **Coverage**: did the close land inside the 68% and 95% bands?
- **Interval score** (primary): band width + (2/α) × how far outside the close landed, in % of the
  previous close (α = 0.32 for the 68% band, 0.05 for the 95% band); lower is better. It rewards
  bands that are both calibrated *and* narrow, so a vaguer model cannot look better by covering more.
- **Range error**: |log(actual range / predicted range)|.
- **Touch Brier**: quality of the P(±1% from the open) forecasts.
- **Direction Brier**: expected ≈ naive.

## Validation before freezing (walk-forward, 500 sessions × 6 cached stocks = 3,000 stock-days)
68% band hit 67% (naive 72%); 95% band hit 94% (naive 92%); range |log error| 0.36 (naive 0.46);
touch Brier 3.5% better than naive; direction skill −0.1% (none, as intended).

## How the live test is judged (100 stock-days)
- 68% band: expected 68% ± 9% (95% binomial range 59–77%). 95% band: 95% ± 4% (91–99%).
- Range error and touch Brier: model should match or beat naive.
- Direction: expected ≈ naive. Any apparent direction skill over 10 days is **not** evidence
  (100 correlated stock-days, same market days).

## Versions: champion vs challengers (fair comparison)
- All versions are registered in `models.json`. The **champion** is the official model;
  **challengers** predict alongside it every morning, so every version is scored on the **same days**.
- A version is never judged on days before its `frozen` date (no grading on the data used to build it).
- `forecast.py leaderboard` writes `leaderboard.md`: one row per version (plus naive), one column per
  metric, on common days only, with **Diebold-Mariano** paired tests on daily mean losses (stocks
  averaged within a day, because they move together). P-values are not reported below 20 common days.
- **Promotion rule** (pre-registered): a challenger replaces the champion only after **≥ 40 common
  live days**, with a lower interval score at **p < 0.05**, coverage inside the binomial range, and
  touch Brier not significantly worse. Historical walk-forward comparisons
  (`backtest --model`, `leaderboard --backtest`) are secondary evidence only.

## Update rules (pre-registered: the only changes allowed after the 2 weeks)
1. **Bands**: only if live 68% coverage falls outside 59–77% or 95% coverage outside 91–99%.
   Refit `band_mult` on live days **plus** the latest 250 historical sessions (so 10 days
   cannot dominate), bounded to 0.8–1.25.
2. **Touch probabilities**: only if live touch Brier is worse than naive. Set `touch_calib`
   = realized touch rate / mean predicted rate, bounded to 0.85–1.15.
3. **Direction**: unchanged. A direction signal can only enter after passing the full lab
   protocol (pre-registered hypothesis → split-half screen → out-of-sample test → replication).
4. Any change becomes **v2**, added to `models.json` as a **challenger** (`status: "challenger"`,
   `frozen: <date>`, only the changed params). **v1 stays champion**; v2 predicts alongside it from the
   next session, and is promoted only by the promotion rule above. Scored days are never rescored or edited.
5. Capital protection first: the forecasts feed risk (expected range, ±1% touch odds), not
   trade signals. Nothing here is a recommendation to trade.

## Universe change, 2026-10-28

TGT (Consumer Staples), WMT (Consumer Staples) and LITE (Information Technology) were added to
universe.csv at the user's request, for the new paper agents. The model is unchanged. From 2026-10-28 each
day has 13 stock-days instead of 10; the leaderboard still compares versions on identical stock-days.

## Two-week review, 2026-10-30

See REVIEW_v1.md. Live coverage (68%: 57%, 95%: 87%) fell outside the binomial ranges and the touch Brier
was slightly worse than naive, so rules 1 and 2 applied. **v2** (band_mult 0.99, touch_calib 1.09) is
registered as a challenger from 2026-11-02; v1 stays champion until the promotion rule says otherwise.

## Universe change, 2026-11-19

SPY and QQQ (sector "Index ETF") were added to universe.csv at the user's request: the forecasts now cover
the two index ETFs, and the season 2 agents may trade them. The model is unchanged. They take effect from the
first morning run after the change is merged (planned 2026-11-19); from then on each day has 15 symbol-days.
ETFs have no earnings reports, so `earnings_cal.py` skips them.
