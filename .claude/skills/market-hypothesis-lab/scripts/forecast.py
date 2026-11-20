# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy", "yfinance>=0.2.40", "requests"]
# ///
"""Live forward test: predict each stock's day BEFORE the open, score it AFTER the close,
and compare model versions fairly (champion vs challengers on identical days). No trades.

Usage (folder = the forecast lab, e.g. lab/forecast, holding universe.csv and models.json):
  uv run forecast.py predict     --dir lab/forecast [--date 2026-10-19]   # all active versions
  uv run forecast.py score       --dir lab/forecast [--date 2026-10-19]
  uv run forecast.py report      --dir lab/forecast                       # champion summary
  uv run forecast.py leaderboard --dir lab/forecast [--backtest]          # versions on common days + DM tests
  uv run forecast.py backtest    --dir lab/forecast --days 500 [--model v2]  # walk-forward on history

Versions live in models.json: {"champion": "v1", "versions": {"v1": {"params": {...}, "status":
"champion", "frozen": "YYYY-MM-DD"}, "v2": {..., "status": "challenger"}}}. Every active version
(champion + challengers) predicts every morning, so all are scored on the SAME days. A
challenger is judged only on days after its own frozen date (never on the data used to build it).

Model family (parameters per version). Only data up to the PREVIOUS close is used.
  sigma      EWMA (lambda) of daily log returns, x band_mult
  P(up)      252-day base rate of up closes shrunk toward 50% (no timing signal: 36 tests found none)
  close band empirical quantiles of r_t / sigma_{t-1} over z_window days (fat tails) x sigma
  range      median (high-low)/prev close / sigma_{t-1} over range_window days x sigma
  touch +1%  frequency over touch_window days that (high/open-1)/sigma_{t-1} >= 0.01/sigma (and -1% low)
Naive baseline scored alongside: 20-day std, normal bands, P(up)=0.5, normal touch formula.

Scores per stock-day: band coverage (68/95), INTERVAL SCORE (width + 2/alpha x miss distance, in % of
the previous close: rewards bands that are both calibrated AND narrow, so "better" can't mean "vaguer"),
range log error, Brier for ±1% touches and for direction.
"""
import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import cache  # noqa: E402

DEFAULT = {"lambda": 0.94, "base_window": 252, "shrink": 0.5, "z_window": 500, "range_window": 252,
           "touch": 0.01, "touch_window": 500, "band_mult": 1.0, "touch_calib": 1.0}
ALPHA = {"68": 0.32, "95": 0.05}
# Pre-registered promotion rule (also in MODEL.md)
PROMOTE = {"min_days": 40, "p": 0.05}
MIN_DM_DAYS = 20  # below this, paired tests are not reported


# ------------------------------------------------------------------ registry
def registry(folder):
    p = Path(folder) / "models.json"
    if not p.exists():  # legacy single-model folder
        return {"champion": "v1", "versions": {"v1": {"params": {}, "status": "champion", "frozen": "2026-10-16"}}}
    return json.loads(p.read_text())


def active_versions(folder):
    reg = registry(folder)
    out = {}
    for v, d in reg["versions"].items():
        if d.get("status") in ("champion", "challenger"):
            out[v] = {**DEFAULT, **d.get("params", {})}
    return reg["champion"], out


# ------------------------------------------------------------------ model
def _ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def ewma_sigma(r, lam):
    s = np.empty(len(r)); v = np.nanvar(r[:60]) if len(r) > 60 else np.nanvar(r)
    for i, x in enumerate(r):
        s[i] = math.sqrt(v)  # sigma known BEFORE return i
        if not np.isnan(x):
            v = lam * v + (1 - lam) * x * x
    return s, math.sqrt(v)


def forecast_one(hist, prm):
    """hist: OHLC up to and including the previous session. Returns model + naive forecasts."""
    c, o, h, l = (hist[k].to_numpy(float) for k in ("Close", "Open", "High", "Low"))
    r = np.diff(np.log(c))
    s_before, s_next = ewma_sigma(r, prm["lambda"])
    s_next *= prm["band_mult"]
    z = (r / s_before)[-int(prm["z_window"]):]
    up = (r[-int(prm["base_window"]):] > 0).mean()
    p_up = 0.5 + prm["shrink"] * (up - 0.5)
    q = np.nanquantile(z, [0.025, 0.16, 0.5, 0.84, 0.975])
    prev = c[-1]
    rng_ratio = ((h[1:] - l[1:]) / c[:-1] / s_before)[-int(prm["range_window"]):]
    up_ex = ((h[1:] / o[1:] - 1) / s_before)[-int(prm["touch_window"]):]
    dn_ex = ((1 - l[1:] / o[1:]) / s_before)[-int(prm["touch_window"]):]
    thr = prm["touch"] / s_next
    p_t_up = float(np.clip((up_ex >= thr).mean() * prm["touch_calib"], 0.01, 0.99))
    p_t_dn = float(np.clip((dn_ex >= thr).mean() * prm["touch_calib"], 0.01, 0.99))
    s20 = float(np.std(r[-20:], ddof=1))
    naive_touch = 2 * (1 - _ncdf(prm["touch"] / max(s20, 1e-9)))
    return {
        "prev_close": prev, "sigma": s_next, "p_up": float(p_up),
        "band68_lo": prev * math.exp(q[1] * s_next), "band68_hi": prev * math.exp(q[3] * s_next),
        "band95_lo": prev * math.exp(q[0] * s_next), "band95_hi": prev * math.exp(q[4] * s_next),
        "median_close": prev * math.exp(q[2] * s_next),
        "exp_range_pct": float(np.nanmedian(rng_ratio) * s_next),
        "p_touch_up1": p_t_up, "p_touch_dn1": p_t_dn,
        "naive_sigma": s20, "naive_p_up": 0.5,
        "naive_band68_lo": prev * math.exp(-s20), "naive_band68_hi": prev * math.exp(s20),
        "naive_band95_lo": prev * math.exp(-1.96 * s20), "naive_band95_hi": prev * math.exp(1.96 * s20),
        "naive_exp_range_pct": 1.6 * s20, "naive_p_touch_up1": min(naive_touch, 0.99),
        "naive_p_touch_dn1": min(naive_touch, 0.99),
    }


def interval_score(lo, hi, y, alpha, ref):
    """Winkler/Gneiting-Raftery interval score in % of ref: width + (2/alpha) x distance outside."""
    s = (hi - lo) + (2 / alpha) * max(lo - y, 0) + (2 / alpha) * max(y - hi, 0)
    return s / ref


def made_before_open(made_at, date):
    """A forecast is valid only if it was made before 09:30 ET on its own session date."""
    if not isinstance(made_at, str) or not made_at:
        return True  # legacy rows / walk-forward backtests carry no timestamp
    return pd.Timestamp(made_at).tz_convert("America/New_York") < pd.Timestamp(f"{date} 09:30", tz="America/New_York")


def with_validity(s):
    s = s.copy()
    s["valid"] = [made_before_open(m, d) for m, d in zip(s.get("made_at", pd.Series([""] * len(s))), s["date"])]
    return s


def score_one(f, bar):
    o, h, l, c = bar["Open"], bar["High"], bar["Low"], bar["Close"]
    up = float(c > f["prev_close"])
    tu, td = float(h >= o * 1.01), float(l <= o * 0.99)
    rng = (h - l) / f["prev_close"]
    s = {"open": o, "high": h, "low": l, "close": c, "ret": c / f["prev_close"] - 1, "went_up": up,
         "touched_up1": tu, "touched_dn1": td, "actual_range_pct": rng}
    for tag in ("", "naive_"):
        s[f"{tag}brier_dir"] = (f[f"{tag}p_up"] - up) ** 2
        for b in ("68", "95"):
            lo, hi = f[f"{tag}band{b}_lo"], f[f"{tag}band{b}_hi"]
            s[f"{tag}in{b}"] = float(lo <= c <= hi)
            s[f"{tag}is{b}"] = interval_score(lo, hi, c, ALPHA[b], f["prev_close"])
        s[f"{tag}range_logerr"] = math.log(rng / f[f"{tag}exp_range_pct"]) if rng > 0 else float("nan")
        s[f"{tag}brier_touch"] = ((f[f"{tag}p_touch_up1"] - tu) ** 2 + (f[f"{tag}p_touch_dn1"] - td) ** 2) / 2
    return s


# ------------------------------------------------------------------ live steps
def _prices(sym, refresh):
    from fetch_data import get_prices  # polite + cached
    p = get_prices(sym, refresh=refresh, max_age_h=1, quiet=True)
    return pd.read_csv(p, index_col=0, parse_dates=True)


def predict(folder, date):
    folder = Path(folder)
    champ, versions = active_versions(folder)
    out = folder / "predictions" / f"{date}.csv"
    if out.exists():
        print(f"{out} already exists: forecasts are written once and never overwritten."); return
    rows = []
    for t in pd.read_csv(folder / "universe.csv").itertuples():
        d = _prices(t.symbol, refresh=True)
        hist = d[d.index < pd.Timestamp(date)].tail(800)  # strictly before the session being predicted
        for ver, prm in versions.items():
            rows.append({"date": date, "symbol": t.symbol, "sector": t.sector, "model": ver,
                         "role": "champion" if ver == champ else "challenger",
                         "data_through": str(hist.index[-1].date()),
                         "made_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                         **forecast_one(hist, prm)})
    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    print(f"Forecasts for {date} (versions {', '.join(versions)}; champion {champ}; "
          f"data through {rows[0]['data_through']}) -> {out}")
    for r in df[df.model == champ].itertuples():
        print(f"  {r.symbol:5} P(up) {r.p_up:.0%} | 68% close {r.band68_lo:9.2f}-{r.band68_hi:9.2f} | exp range "
              f"{r.exp_range_pct:5.1%} | P(+1% from open) {r.p_touch_up1:.0%} | P(-1%) {r.p_touch_dn1:.0%}")


def score(folder, date):
    folder = Path(folder)
    pf = folder / "predictions" / f"{date}.csv"
    if not pf.exists():
        print(f"No forecasts for {date}; nothing to score."); return
    card = folder / "scorecard.csv"
    if card.exists() and (pd.read_csv(card)["date"] == date).any():
        print(f"{date} already scored."); return
    fc = pd.read_csv(pf)
    if "model" not in fc:
        fc["model"] = "v1"
    if "role" not in fc:
        fc["role"] = "champion"
    rows, bars = [], {}
    for f in fc.to_dict("records"):
        if f["symbol"] not in bars:
            d = _prices(f["symbol"], refresh=True)
            bars[f["symbol"]] = d.loc[pd.Timestamp(date)] if pd.Timestamp(date) in d.index else None
            if bars[f["symbol"]] is None:
                print(f"  {f['symbol']}: no bar for {date} (market closed or data not published yet)")
        if bars[f["symbol"]] is None:
            continue
        rows.append({**{k: f[k] for k in ("date", "symbol", "sector", "model", "role")},
                     "made_at": f.get("made_at", ""), **score_one(f, bars[f["symbol"]])})
    if not rows:
        print("Nothing scored (no session data). Re-run later."); return
    s = with_validity(pd.DataFrame(rows))
    old = pd.read_csv(card) if card.exists() else None
    (pd.concat([old, s], ignore_index=True) if old is not None else s).to_csv(card, index=False)
    champ = fc[fc.role == "champion"].model.iloc[0]
    cs, cf = s[s.model == champ], fc[fc.model == champ].set_index("symbol")
    lines = [f"# {date}: forecast vs actual (champion {champ}; versions scored: {', '.join(sorted(s.model.unique()))})", "",
             "| Stock | Return | P(up) | In 68% band | In 95% | Interval score 95 | Range actual vs exp | +1% touched (P) | -1% touched (P) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in cs.to_dict("records"):
        f = cf.loc[r["symbol"]]
        lines.append(f"| {r['symbol']} | {r['ret']:+.2%} | {f['p_up']:.0%} | {'✅' if r['in68'] else '❌'} | "
                     f"{'✅' if r['in95'] else '❌'} | {r['is95']:.1%} | {r['actual_range_pct']:.1%} vs {f['exp_range_pct']:.1%} | "
                     f"{'yes' if r['touched_up1'] else 'no'} ({f['p_touch_up1']:.0%}) | {'yes' if r['touched_dn1'] else 'no'} ({f['p_touch_dn1']:.0%}) |")
    late = cs[~cs.valid]
    if len(late):
        latest = max(pd.Timestamp(m).tz_convert("America/New_York") for m in late.made_at)
        lines += ["", f"⚠️ **{len(late)} of {len(cs)} forecasts were made at or after the 09:30 open** (latest {latest:%H:%M} ET). "
                      "They are shown for the record but EXCLUDED from all scores, the report and the leaderboard."]
    if cs.valid.any():
        lines += ["", summary_lines(cs[cs.valid])]
    (folder / "daily").mkdir(exist_ok=True)
    (folder / "daily" / f"{date}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def summary_lines(s):
    def sk(m, n):  # skill score: 1 - model/naive (positive = model better)
        return 1 - s[m].mean() / s[n].mean() if s[n].mean() > 0 else float("nan")
    return (f"**{len(s)} stock-days.** Close inside 68% band: model {s.in68.mean():.0%} / naive {s.naive_in68.mean():.0%} "
            f"(target 68%); inside 95%: {s.in95.mean():.0%} / {s.naive_in95.mean():.0%} (target 95%). "
            f"Interval score (lower = better): 68% {s.is68.mean():.2%} / naive {s.naive_is68.mean():.2%}, "
            f"95% {s.is95.mean():.2%} / naive {s.naive_is95.mean():.2%}. "
            f"Range error |log|: {s.range_logerr.abs().mean():.2f} / {s.naive_range_logerr.abs().mean():.2f}. "
            f"Skill vs naive (Brier, +ve = model better): direction {sk('brier_dir', 'naive_brier_dir'):+.1%}, "
            f"±1% touches {sk('brier_touch', 'naive_brier_touch'):+.1%}.")


def report(folder):
    card = Path(folder) / "scorecard.csv"
    if not card.exists():
        print("No scored days yet."); return
    s = with_validity(pd.read_csv(card))
    if "model" not in s:
        s["model"] = "v1"
    champ = registry(folder)["champion"]
    s = s[s.model == champ]
    bad = sorted(s[~s.valid].date.unique())
    if bad:
        print(f"Excluded (forecast made after the open): {', '.join(bad)}")
    s = s[s.valid]
    if s.empty:
        print("No valid scored days yet."); return
    print(f"Champion {champ}: {s.date.nunique()} scored days ({s.date.min()} -> {s.date.max()})")
    print(summary_lines(s))
    n = len(s)
    for lvl, col in ((0.68, "in68"), (0.95, "in95")):
        k = s[col].sum(); se = math.sqrt(lvl * (1 - lvl) / n)
        print(f"  {col}: {int(k)}/{n} = {k / n:.0%}; expected {lvl:.0%} ± {1.96 * se:.0%} (95% binomial range)")
    print(f"  realised touch rates: +1% {s.touched_up1.mean():.0%}, -1% {s.touched_dn1.mean():.0%}")
    print("Per stock (68% hits, mean interval score 95, mean |range log error|):")
    print(s.groupby("symbol").agg(days=("date", "count"), in68=("in68", "mean"), is95=("is95", "mean"),
                                  range_err=("range_logerr", lambda x: x.abs().mean())).round(3).to_string())


# ------------------------------------------------------------------ fair comparison
LOSSES = {"interval": lambda d: (d["is68"] + d["is95"]) / 2, "touch": lambda d: d["brier_touch"],
          "range": lambda d: d["range_logerr"].abs(), "direction": lambda d: d["brier_dir"]}


def _as_version(s, ver):
    """Rows for one version; 'naive' is the baseline columns of the champion rows."""
    if ver != "naive":
        return s[s.model == ver]
    base = s[s.role == "champion"].copy()
    for c in [c for c in base.columns if c.startswith("naive_")]:
        base[c[6:]] = base[c]
    base["model"] = "naive"
    return base


def diebold_mariano(a, b, loss):
    """Paired test on DAILY mean loss (stocks averaged within each day, because they share the
    market and are correlated). d_t = loss_a - loss_b; negative mean = a better. 1-step forecasts:
    HAC variance with lag 0. Returns (mean_diff, DM stat, two-sided p, n_days)."""
    la = a.assign(L=LOSSES[loss](a)).groupby("date").L.mean()
    lb = b.assign(L=LOSSES[loss](b)).groupby("date").L.mean()
    d = (la - lb).dropna()
    n = len(d)
    if n < MIN_DM_DAYS or d.std(ddof=1) == 0:  # too few days: a p-value would be noise dressed as proof
        return float(d.mean()) if n else float("nan"), float("nan"), float("nan"), n
    stat = d.mean() / (d.std(ddof=1) / math.sqrt(n))
    p = 2 * (1 - _ncdf(abs(stat)))  # normal approximation; conservative wording in reports
    return float(d.mean()), float(stat), float(p), n


def leaderboard(folder, use_backtest=False):
    folder = Path(folder)
    reg = registry(folder)
    champ = reg["champion"]
    excluded = []
    if use_backtest:
        frames = [pd.read_csv(p).assign(role=lambda x, v=p.stem.split("_")[-1]: "champion" if v == champ else "challenger")
                  for p in folder.glob("backtest_scorecard_*.csv")]
        if not frames:
            print("No backtest scorecards (run backtest --model <ver> first)."); return
        s = pd.concat(frames, ignore_index=True); title = "HISTORICAL walk-forward (secondary evidence)"
    else:
        card = folder / "scorecard.csv"
        if not card.exists():
            print("No scored days yet."); return
        s = with_validity(pd.read_csv(card)); title = "LIVE"
        if "model" not in s:
            s["model"], s["role"] = "v1", "champion"
        excluded = sorted(s[~s.valid].date.unique())
        s = s[s.valid]
    versions = [v for v in reg["versions"] if v in set(s.model)] + ["naive"]
    rows, lines = [], [f"# Forecast leaderboard ({title})", ""]
    for v in versions:
        d = _as_version(s, v)
        frozen = reg["versions"].get(v, {}).get("frozen", "")
        if frozen and not use_backtest:  # never judge a version on days before it was frozen
            d = d[d.date > frozen] if v != reg["champion"] else d
        rows.append((v, d))
    # common days: every compared version must have a score on the day
    common = set.intersection(*[set(d.date) for _, d in rows]) if rows else set()
    if not use_backtest and excluded:
        lines.append(f"Excluded days (forecast made at/after the open): {', '.join(excluded)}.")
    lines.append(f"Common days: {len(common)}"
                 + (f" ({min(common)} → {max(common)})" if common else "") + ". All metrics on identical days; lower is better except coverage.")
    lines += ["", "| Version | Status | Days | Stock-days | 68% cov | 95% cov | Interval 68 | Interval 95 | Range err | Touch Brier | Direction Brier |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    table = {}
    for v, d in rows:
        d = d[d.date.isin(common)]
        table[v] = d
        st = "baseline" if v == "naive" else reg["versions"][v].get("status", "")
        if not len(d):
            lines.append(f"| {v} | {st} | 0 | 0 | | | | | | | |"); continue
        lines.append(f"| {v} | {st} | {d.date.nunique()} | {len(d)} | {d.in68.mean():.0%} | {d.in95.mean():.0%} | "
                     f"{d.is68.mean():.2%} | {d.is95.mean():.2%} | {d.range_logerr.abs().mean():.3f} | "
                     f"{d.brier_touch.mean():.4f} | {d.brier_dir.mean():.4f} |")
    lines += ["", "## Paired tests vs champion (Diebold-Mariano on daily mean loss; negative diff = challenger better)", "",
              "| Challenger | Loss | Mean diff | DM stat | p | Days |", "|---|---|---|---|---|---|"]
    verdicts = []
    for v, d in table.items():
        if v == champ or not len(d):
            continue
        for loss in LOSSES:
            md, stat, p, n = diebold_mariano(d, table[champ], loss)
            lines.append(f"| {v} | {loss} | {md:+.5f} | " + (f"{stat:+.2f} | {p:.3f}" if p == p else
                         f"n/a | n/a (needs {MIN_DM_DAYS}+ days)") + f" | {n} |")
        if v != "naive" and not use_backtest:
            md, stat, p, n = diebold_mariano(d, table[champ], "interval")
            cov_ok = abs(d.in68.mean() - 0.68) <= 1.96 * math.sqrt(0.68 * 0.32 / max(len(d), 1)) and \
                abs(d.in95.mean() - 0.95) <= 1.96 * math.sqrt(0.95 * 0.05 / max(len(d), 1))
            t_md, _, t_p, _ = diebold_mariano(d, table[champ], "touch")
            ready = n >= PROMOTE["min_days"]
            win = md < 0 and p == p and p < PROMOTE["p"] and cov_ok and not (t_md > 0 and t_p == t_p and t_p < PROMOTE["p"])
            verdicts.append(f"- **{v}**: {'PROMOTE (replace champion)' if ready and win else 'not yet' if not ready else 'KEEP champion'} "
                            f"- {n}/{PROMOTE['min_days']} common days; interval diff {md:+.5f} "
                            + (f"(p={p:.3f}); " if p == p else "(p not reported yet); ") + 
                            f"coverage {'OK' if cov_ok else 'outside range'}; touch {'WORSE' if (t_md > 0 and t_p == t_p and t_p < 0.05) else 'not worse'}")
    lines += ["", "## Promotion verdicts (pre-registered rule: >=40 common days, interval score better at p<0.05, "
              "coverage inside binomial range, touch Brier not significantly worse)", ""] + (
        ["- Historical comparison is secondary evidence only: promotion is decided on LIVE days."] if use_backtest
        else verdicts or ["- no challengers"])
    out = folder / ("leaderboard_backtest.md" if use_backtest else "leaderboard.md")
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def backtest(folder, days, model=None):
    """Walk-forward on history for one version: what calibration should look like."""
    folder = Path(folder)
    champ, versions = active_versions(folder)
    ver = model or champ
    reg = registry(folder)
    prm = {**DEFAULT, **reg["versions"][ver].get("params", {})}
    rows = []
    for t in pd.read_csv(folder / "universe.csv").itertuples():
        p = cache.ROOT / f"prices/{cache.safe(t.symbol)}.csv"
        if not p.exists():
            print(f"  {t.symbol}: not cached yet, skipped"); continue
        d = pd.read_csv(p, index_col=0, parse_dates=True)
        for i in range(len(d) - days, len(d)):
            f = forecast_one(d.iloc[max(0, i - 800):i], prm)
            rows.append({"date": str(d.index[i].date()), "symbol": t.symbol, "sector": t.sector, "model": ver,
                         **score_one(f, d.iloc[i])})
    s = pd.DataFrame(rows)
    s.to_csv(folder / f"backtest_scorecard_{ver}.csv", index=False)
    print(f"Walk-forward backtest {ver}, last {days} sessions x {s.symbol.nunique()} stocks:")
    print(summary_lines(s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["predict", "score", "report", "leaderboard", "backtest"])
    ap.add_argument("--dir", required=True)
    ap.add_argument("--date", default=pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d"))
    ap.add_argument("--days", type=int, default=500)
    ap.add_argument("--model")
    ap.add_argument("--backtest", action="store_true")
    a = ap.parse_args()
    {"predict": lambda: predict(a.dir, a.date), "score": lambda: score(a.dir, a.date),
     "report": lambda: report(a.dir), "leaderboard": lambda: leaderboard(a.dir, a.backtest),
     "backtest": lambda: backtest(a.dir, a.days, a.model)}[a.cmd]()


if __name__ == "__main__":
    main()
