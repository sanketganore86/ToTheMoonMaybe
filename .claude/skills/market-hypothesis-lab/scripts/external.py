# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy", "yfinance>=0.2.40", "requests"]
# ///
"""Score OTHER people's trade calls (social media, newsletters, alert bots) against our model.

Two kinds: option calls (C###, calls.csv) and stock plans (P###, plans.csv: long/short with an optional
trigger, a stop and a target; see the "Stock plans" section below).

Outside calls are never fed into our frozen model or the paper agents (that would contaminate
the test). Instead each call is recorded BEFORE the open with our model's odds, and scored
after expiry. Over many calls this shows whose calls beat our model's odds.

Usage (dir = e.g. lab/external):
  uv run external.py add   --dir lab/external --source "SourceA" --symbol AMD --strike 515 --kind P \
                           --expiry 2026-10-23 --said "SourceA post: AMD 515P 10/23, semis weakness"
  uv run external.py score --dir lab/external [--date 2026-10-23]   # scores every call expired by --date
  uv run external.py report --dir lab/external                      # per-source summary

Odds at recording time (zero drift, our model's volatility; data through the last close before
the first session after recording):
  P(ITM at expiry)       lognormal with EWMA(0.94) daily sigma x sqrt(trading days to expiry)
  P(touch strike)        reflection approximation, 2 x P(ITM), capped at 1
  model premium          Black-Scholes with options.py's implied-vol model (MODELED, not a quote)
  P(profit at expiry)    P(finishing beyond strike +/- model premium), held to expiry
Scoring after expiry (daily bars): close at expiry, in the money or not, intrinsic value, return
if bought at the model premium and held to expiry, best intrinsic value reached before expiry
(HINDSIGHT: shows the most anyone could have captured, not a realistic exit), and the Brier
score of our P(ITM) forecast. Option results are MODELED: no real option prices are used.

Stock plans (e.g. "short after a completed 1h close below 500, stop 510, target 450"):
  uv run external.py plan --dir lab/external --source SourceA --symbol MSFT --side short \
      --trigger close_below --trigger-price 500 --tf 1h --stop 510 --target 450 \
      --entry 500 --trigger-days 5 --hold-days 20 --said "..."
  --trigger none enters at the first session's open; --hold-days 0 means flat at that day's close.
  Odds at recording: 4,000 zero-drift random paths at our EWMA volatility on 15-minute steps:
  P(trigger fires within --trigger-days sessions), and once in, P(target first), P(stop first),
  P(neither by the end of --hold-days sessions). Scored nightly by `score` on real 1-minute bars
  (paper.intraday, cached): the trigger bar is the completed 15m/1h bar (aligned to 09:30) or the
  daily close; entry at the NEXT minute's open (or the next session's open); stop and target are
  checked minute by minute, stop first when one bar touches both, gaps fill at the worse open;
  0.05% cost each way. Yahoo keeps 1-minute bars for about 30 days, so plans are scored while they run.
"""
import argparse
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import cache  # noqa: E402
import options as op  # noqa: E402

ET = "America/New_York"


def _N(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _ewma_sigma(close, lam=0.94):
    r = np.diff(np.log(close))
    v = np.var(r[:60])
    for x in r:
        v = lam * v + (1 - lam) * x * x
    return math.sqrt(v)


def _daily(symbol, refresh=True):
    from fetch_data import get_prices  # polite + cached
    p = get_prices(symbol, refresh=refresh, max_age_h=6, quiet=True)
    return pd.read_csv(p, index_col=0, parse_dates=True)


def odds(d, strike, kind, expiry, asof_session):
    """Model odds using data strictly before asof_session (the first session the call can be acted on)."""
    hist = d[d.index < pd.Timestamp(asof_session)]
    S = float(hist.Close.iloc[-1])
    days = len(pd.bdate_range(asof_session, expiry))  # trading days from first session to expiry, inclusive
    sig = _ewma_sigma(hist.Close.to_numpy()) * math.sqrt(max(days, 1))
    z = math.log(strike / S) / sig
    p_itm = 1 - _N(z) if kind == "C" else _N(z)
    from paper import risk_free_rate  # downloads ^IRX politely if this machine lacks it
    r = risk_free_rate(asof_session)
    iv = float(op.atm_iv_series(hist).iloc[-1])
    T = (pd.Timestamp(expiry) - hist.index[-1]).days / 365
    prem = op.bs(S, strike, T, r, op.iv_at(iv, S, strike), kind)
    be = strike + prem if kind == "C" else strike - prem
    zb = math.log(be / S) / sig
    p_prof = 1 - _N(zb) if kind == "C" else _N(zb)
    return {"data_through": str(hist.index[-1].date()), "spot": round(S, 2), "move_needed": strike / S - 1,
            "trading_days": days, "p_itm": p_itm, "p_touch": min(1.0, 2 * p_itm), "model_premium": round(prem, 2),
            "breakeven": round(be, 2), "p_profit": p_prof}


def add(folder, source, symbol, strike, kind, expiry, said, note=""):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz=ET)
    if now.weekday() < 5 and pd.Timestamp("09:30").time() <= now.time() < pd.Timestamp("16:15").time():
        # the odds use "the last close before the first session"; during the session that close does not
        # exist yet, and today's partial bar would stand in for it. Record before 09:30 or after 16:15 ET.
        print(f"{now:%H:%M} ET is during the session: record before 09:30 or after 16:15 ET (nothing recorded)")
        return
    # first session the call can be acted on: today if before the open, else the next business day
    first = now.normalize().tz_localize(None)
    if now.weekday() >= 5 or now.time() >= pd.Timestamp("09:30").time():
        first = first + pd.tseries.offsets.BDay(1)
    first = str(pd.Timestamp(first).date())
    o = odds(_daily(symbol), strike, kind, expiry, first)
    calls = folder / "calls.csv"
    old = pd.read_csv(calls) if calls.exists() else pd.DataFrame()
    cid = f"C{len(old) + 1:03d}"
    row = {"id": cid, "recorded_at": now.isoformat(timespec="seconds"), "first_session": first,
           "recorded_before_open": True, "source": source, "symbol": symbol.upper(), "strike": strike,
           "kind": kind, "expiry": expiry, "said": said, "note": note, **o}
    pd.concat([old, pd.DataFrame([row])], ignore_index=True).to_csv(calls, index=False)
    print(f"{cid} {source}: {symbol} {strike:g}{kind} {expiry} | spot {o['spot']} (through {o['data_through']}), "
          f"needs {o['move_needed']:+.1%} | P(ITM) {o['p_itm']:.0%}, P(touch) {o['p_touch']:.0%}, "
          f"model premium {o['model_premium']}, P(profit) {o['p_profit']:.0%}")


# ------------------------------------------------------------------ stock plans
COST = 0.0005          # per side
SPD = 26               # 15-minute steps per session in the odds simulation
TF_STEPS = {"15m": 1, "1h": 4, "1d": SPD}


def _first_session(now):
    """None during the session (record before 09:30 or after 16:15 ET), else the first session the idea can be acted on."""
    if now.weekday() < 5 and pd.Timestamp("09:30").time() <= now.time() < pd.Timestamp("16:15").time():
        return None
    first = now.normalize().tz_localize(None)
    if now.weekday() >= 5 or now.time() >= pd.Timestamp("09:30").time():
        first = first + pd.tseries.offsets.BDay(1)
    return str(pd.Timestamp(first).date())


def plan_odds(S0, sig_d, p, n=4000, seed=7):
    """Zero-drift random paths on 15-minute steps. Returns P(trigger) and, once triggered, P(target/stop/neither first)."""
    rng = np.random.default_rng(seed)
    s = sig_d / math.sqrt(SPD)
    tdays, hdays = int(p["trigger_days"]), int(p["hold_days"])
    T = (tdays + hdays + 1) * SPD
    paths = S0 * np.exp(np.cumsum(rng.normal(-0.5 * s * s, s, (n, T)), axis=1))
    short = p["side"] == "short"
    out = {"trig": 0, "target": 0, "stop": 0, "time": 0}
    rets = []
    for x in paths:
        if p["trigger"] == "none":
            i, e = -1, S0
        else:
            k = TF_STEPS[p["tf"]]
            idx = np.arange(k - 1, tdays * SPD, k)
            c = x[idx]
            hit = np.where(c < p["trigger_price"])[0] if p["trigger"] == "close_below" else np.where(c > p["trigger_price"])[0]
            if not len(hit):
                continue
            i = int(idx[hit[0]]); e = x[i]
        out["trig"] += 1
        end = ((max(i, 0) // SPD) + 1 + hdays) * SPD
        seg = x[i + 1:end]
        st = np.where(seg >= p["stop"])[0] if short else np.where(seg <= p["stop"])[0]
        tg = np.where(seg <= p["target"])[0] if short else np.where(seg >= p["target"])[0]
        a, b = (st[0] if len(st) else 10**9), (tg[0] if len(tg) else 10**9)
        if a == b == 10**9:
            out["time"] += 1; xx = seg[-1] if len(seg) else e
        elif a <= b:
            out["stop"] += 1; xx = p["stop"]
        else:
            out["target"] += 1; xx = p["target"]
        rets.append((e / xx - 1) if short else (xx / e - 1))
    t = max(out["trig"], 1)
    return {"p_trigger": out["trig"] / n, "p_target": out["target"] / t, "p_stop": out["stop"] / t,
            "p_neither": out["time"] / t, "model_avg_ret": float(np.mean(rets)) if rets else float("nan")}


def plan_add(folder, a):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    now = pd.Timestamp.now(tz=ET)
    first = _first_session(now)
    if first is None:
        print(f"{now:%H:%M} ET is during the session: record before 09:30 or after 16:15 ET (nothing recorded)"); return
    side = a.side
    if (side == "short" and not a.target < a.stop) or (side == "long" and not a.target > a.stop):
        print("target and stop are on the wrong sides for a", side); return
    if a.trigger != "none" and a.trigger_price is None:
        print("--trigger-price is needed with --trigger", a.trigger); return
    d = _daily(a.symbol)
    hist = d[d.index < pd.Timestamp(first)]
    S0 = float(hist.Close.iloc[-1]); sig = _ewma_sigma(hist.Close.to_numpy())
    p = {"side": side, "trigger": a.trigger, "trigger_price": a.trigger_price, "tf": a.tf,
         "stop": a.stop, "target": a.target, "trigger_days": a.trigger_days, "hold_days": a.hold_days}
    o = plan_odds(S0, sig, p)
    ref = a.entry or (a.trigger_price if a.trigger != "none" else S0)
    risk = abs(ref - a.stop) / ref; reward = abs(a.target - ref) / ref
    plans = folder / "plans.csv"
    old = pd.read_csv(plans) if plans.exists() else pd.DataFrame()
    pid = f"P{len(old) + 1:03d}"
    row = {"id": pid, "recorded_at": now.isoformat(timespec="seconds"), "first_session": first, "source": a.source,
           "symbol": a.symbol.upper(), "side": side, "trigger": a.trigger,
           "trigger_price": a.trigger_price if a.trigger != "none" else "", "tf": a.tf if a.trigger != "none" else "",
           "entry_stated": a.entry or "", "stop": a.stop, "target": a.target, "trigger_days": a.trigger_days,
           "hold_days": a.hold_days, "said": a.said, "note": a.note, "data_through": str(hist.index[-1].date()),
           "spot": round(S0, 2), "daily_sigma": round(sig, 4), "risk_pct": round(risk, 4), "reward_pct": round(reward, 4),
           "stated_rr": round(reward / risk, 2) if risk else "", **{k: round(v, 4) for k, v in o.items()}}
    pd.concat([old, pd.DataFrame([row])], ignore_index=True).to_csv(plans, index=False)
    trig = "at the open" if a.trigger == "none" else f"after a {a.tf} {a.trigger.replace('_', ' ')} {a.trigger_price}"
    print(f"{pid} {a.source}: {side} {a.symbol.upper()} {trig}, stop {a.stop}, target {a.target} | spot {S0:.2f} "
          f"(through {row['data_through']}), daily sigma {sig:.1%} | risk {risk:.1%}, reward {reward:.1%} (R:R {row['stated_rr']}) | "
          f"P(trigger in {a.trigger_days}d) {o['p_trigger']:.0%}; once in: target first {o['p_target']:.1%}, "
          f"stop first {o['p_stop']:.0%}, neither in {a.hold_days}d {o['p_neither']:.0%}")
    report(folder)


def _session(symbol, day):
    from paper import intraday
    try:
        b = intraday(symbol, day)
    except Exception as ex:  # noqa: BLE001
        print(f"  {symbol} {day}: 1-minute bars unavailable ({type(ex).__name__})"); return None
    return b.between_time("09:30", "15:59") if len(b) else b


def plan_walk(p, sessions):
    """Replay one plan on real 1-minute bars. sessions: list of (date, bars). Returns a final result dict, or, while the
    plan is still running, a live status whose "status" is in RUNNING (see _plan_live)."""
    short = p["side"] == "short"
    sgn = -1 if short else 1
    stop, target = float(p["stop"]), float(p["target"])
    entry = None; pending = False; tsess = 0; held = -1; lo = hi = None; last = last_day = None
    for day, b in sessions:
        if b is None or b.empty:
            continue
        last, last_day = float(b.Close.iloc[-1]), str(day)
        start = None
        if entry is None:
            if pending or p["trigger"] == "none":
                start = 0
            else:
                tsess += 1
                tp = float(p["trigger_price"])
                below = p["trigger"] == "close_below"
                if p["tf"] == "1d":
                    c = float(b.Close.iloc[-1])
                    if (c < tp) if below else (c > tp):
                        pending = True; trig_at = f"{day} close {c:.2f}"
                else:
                    rs = b.resample(p["tf"].replace("m", "min"), origin=pd.Timestamp(f"{day} 09:30"), label="left",
                                    closed="left").agg({"Close": "last"}).dropna()
                    step = pd.Timedelta(p["tf"].replace("m", "min"))
                    for t, c in rs.Close.items():
                        bar_end = min(t + step, pd.Timestamp(f"{day} 16:00"))
                        if (c < tp) if below else (c > tp):
                            trig_at = f"{t:%Y-%m-%d %H:%M} bar close {c:.2f}"
                            nxt = np.where(b.index >= bar_end)[0]
                            if len(nxt):
                                start = int(nxt[0])
                            else:
                                pending = True
                            break
                if start is None and not pending and tsess >= int(p["trigger_days"]):
                    return {"status": "not triggered", "trigger_at": "", "entry_time": "", "entry": "", "exit_time": "",
                            "exit": "", "ret": 0.0, "r_multiple": 0.0, "best_move_hindsight": "", "resolved": str(day)}
            if start is not None:
                entry = float(b.Open.iloc[start]); entry_t = b.index[start]; held = 0
                if p["trigger"] == "none":
                    trig_at = "at the open"
        else:
            start = 0; held += 1
        if entry is None:
            continue
        for t, r in b.iloc[start:].iterrows():
            lo = r.Low if lo is None else min(lo, r.Low); hi = r.High if hi is None else max(hi, r.High)
            hit_stop = r.High >= stop if short else r.Low <= stop
            hit_tgt = r.Low <= target if short else r.High >= target
            if hit_stop:
                x = max(stop, r.Open) if short else min(stop, r.Open); why = "stop"
            elif hit_tgt:
                x = min(target, r.Open) if short else max(target, r.Open); why = "target"
            else:
                continue
            return _plan_result(why, trig_at, entry_t, entry, t, x, sgn, stop, lo, hi, day)
        if held >= int(p["hold_days"]):
            return _plan_result("time exit", trig_at, entry_t, entry, b.index[-1], float(b.Close.iloc[-1]), sgn, stop, lo, hi, day)
    if entry is None:
        return {"status": "triggered, enters next open" if pending else "waiting for trigger",
                "trigger_at": trig_at if pending else "", "sessions_left": max(int(p["trigger_days"]) - tsess, 0),
                "last_close": round(last, 2) if last is not None else "", "as_of": last_day or ""}
    return _plan_live(p, trig_at, entry_t, entry, last, lo, hi, sgn, stop, target, held, last_day)


RUNNING = ("waiting for trigger", "triggered, enters next open", "open")


def _plan_live(p, trig_at, et, e, last, lo, hi, sgn, stop, target, held, day):
    """Status of a plan that is in a position: marked to the last close (exit cost included), and how close it came to its stop."""
    e, last, lo, hi = float(e), float(last), float(lo), float(hi)
    worst = hi if sgn < 0 else lo  # the price furthest against the position since entry
    return {"status": "open", "trigger_at": trig_at, "entry_time": f"{et:%Y-%m-%d %H:%M}", "entry": round(e, 2),
            "last_close": round(last, 2), "open_ret": round(sgn * (last / e - 1) - 2 * COST, 5),
            "worst_price": round(worst, 2), "worst_ret": round(sgn * (worst / e - 1), 5),
            "stop_gap_pct": round(abs(stop - worst) / e, 5), "to_target_pct": round(sgn * (target / last - 1), 5),
            "sessions_left": max(int(p["hold_days"]) - held, 0), "as_of": day}


def _plan_result(why, trig_at, et, e, xt, x, sgn, stop, lo, hi, day):
    e, x, lo, hi = float(e), float(x), float(lo), float(hi)
    gross = sgn * (x / e - 1)
    best = (e - lo) / e if sgn < 0 else (hi - e) / e
    return {"status": why, "trigger_at": trig_at, "entry_time": f"{et:%Y-%m-%d %H:%M}", "entry": round(e, 2),
            "exit_time": f"{xt:%Y-%m-%d %H:%M}", "exit": round(x, 2), "ret": round(gross - 2 * COST, 5),
            "r_multiple": round(gross / (abs(e - stop) / e), 2) if e != stop else "",
            "best_move_hindsight": round(best, 4), "resolved": str(day)}


def plan_score(folder, date):
    folder = Path(folder)
    plans_p, card_p = folder / "plans.csv", folder / "plans_scorecard.csv"
    if not plans_p.exists():
        return []
    plans = pd.read_csv(plans_p, keep_default_na=False)
    done = set(pd.read_csv(card_p).id) if card_p.exists() else set()
    now = pd.Timestamp.now(tz=ET)
    last = pd.Timestamp(date)
    if now < pd.Timestamp(f"{date} 16:15", tz=ET):
        last = last - pd.tseries.offsets.BDay(1)
    rows, live = [], []
    for p in plans.to_dict("records"):
        if p["id"] in done or pd.Timestamp(p["first_session"]) > last:
            continue
        days = [str(d.date()) for d in pd.bdate_range(p["first_session"], last)]
        res = plan_walk(p, [(d, _session(p["symbol"], d)) for d in days])
        if res["status"] in RUNNING:
            live.append({"id": p["id"], "source": p["source"], "symbol": p["symbol"], "side": p["side"],
                         "stop": p["stop"], "target": p["target"], **res})
            print(f"{p['id']} {p['source']} {p['side']} {p['symbol']}: {res['status']} as of {res['as_of']}"
                  + (f", entry {res['entry']} -> close {res['last_close']} ({res['open_ret']:+.2%})" if res["status"] == "open" else ""))
            continue
        hit = 1.0 if res["status"] == "target" else 0.0
        rows.append({"id": p["id"], "source": p["source"], "symbol": p["symbol"], "side": p["side"], **res,
                     "model_p_trigger": p["p_trigger"], "model_p_target": p["p_target"],
                     "brier_p_target": (p["p_target"] - hit) ** 2 if res["status"] != "not triggered" else "",
                     "scored_at": datetime.now().astimezone().isoformat(timespec="seconds")})
        print(f"{p['id']} {p['source']} {p['side']} {p['symbol']}: {res['status']} "
              + (f"entry {res['entry']} ({res['entry_time']}) -> {res['exit']} ({res['exit_time']}), {res['ret']:+.2%}, "
                 f"{res['r_multiple']}R" if res["status"] != "not triggered" else f"(by {res['resolved']})"))
    if rows:
        old = pd.read_csv(card_p) if card_p.exists() else None
        s = pd.DataFrame(rows)
        (pd.concat([old, s], ignore_index=True) if old is not None else s).to_csv(card_p, index=False)
    # a snapshot, rewritten each night (the scorecard above stays append-only): plans still waiting or in a position
    live_p = folder / "plans_live.csv"
    if live:
        pd.DataFrame(live).to_csv(live_p, index=False)
    elif live_p.exists():
        live_p.unlink()
    return rows


def score(folder, date):
    plan_score(folder, date)
    _score_calls(folder, date)
    if (Path(folder) / "plans.csv").exists():
        report(folder)  # open plans' status changes every night, even when nothing finished


def _score_calls(folder, date):
    folder = Path(folder)
    calls_p, card_p = folder / "calls.csv", folder / "scorecard.csv"
    if not calls_p.exists():
        print("No calls recorded."); return
    calls = pd.read_csv(calls_p)
    done = set(pd.read_csv(card_p).id) if card_p.exists() else set()
    rows = []
    for c in calls.to_dict("records"):
        if c["id"] in done or c["expiry"] > date:
            continue
        if pd.Timestamp.now(tz=ET) < pd.Timestamp(f"{c['expiry']} 16:15", tz=ET):
            print(f"{c['id']}: expiry {c['expiry']} has not closed yet; not scored"); continue
        d = _daily(c["symbol"])
        w = d[(d.index >= pd.Timestamp(c["first_session"])) & (d.index <= pd.Timestamp(c["expiry"]))]
        if len(w) == 0 or w.index[-1] < pd.Timestamp(c["expiry"]) - pd.Timedelta(days=3):
            print(f"{c['id']}: no bars up to {c['expiry']} yet"); continue
        K, k = c["strike"], c["kind"]
        S_exp = float(w.Close.iloc[-1])
        intrinsic = max(S_exp - K, 0) if k == "C" else max(K - S_exp, 0)
        best = max(float(w.High.max()) - K, 0) if k == "C" else max(K - float(w.Low.min()), 0)
        itm = float(intrinsic > 0)
        rows.append({"id": c["id"], "source": c["source"], "symbol": c["symbol"], "contract": f"{K:g}{k} {c['expiry']}",
                     "expiry_close": round(S_exp, 2), "last_bar": str(w.index[-1].date()), "itm": itm,
                     "intrinsic": round(intrinsic, 2), "model_premium": c["model_premium"],
                     "held_to_expiry_return": intrinsic / c["model_premium"] - 1 if c["model_premium"] > 0 else float("nan"),
                     "best_intrinsic_hindsight": round(best, 2),
                     "best_return_hindsight": best / c["model_premium"] - 1 if c["model_premium"] > 0 else float("nan"),
                     "model_p_itm": c["p_itm"], "brier_p_itm": (c["p_itm"] - itm) ** 2,
                     "scored_at": datetime.now().astimezone().isoformat(timespec="seconds")})
    if not rows:
        print(f"No calls expired by {date} left to score."); return
    s = pd.DataFrame(rows)
    old = pd.read_csv(card_p) if card_p.exists() else None
    (pd.concat([old, s], ignore_index=True) if old is not None else s).to_csv(card_p, index=False)
    for r in rows:
        print(f"{r['id']} {r['source']} {r['symbol']} {r['contract']}: close {r['expiry_close']} -> "
              f"{'ITM' if r['itm'] else 'expired worthless'}; held to expiry {r['held_to_expiry_return']:+.0%} "
              f"(model premium); best possible {r['best_return_hindsight']:+.0%} (hindsight); our P(ITM) was {r['model_p_itm']:.0%}")
    report(folder)


def report(folder):
    folder = Path(folder)
    calls = pd.read_csv(folder / "calls.csv")
    card = pd.read_csv(folder / "scorecard.csv") if (folder / "scorecard.csv").exists() else pd.DataFrame()
    lines = ["# External calls vs our model", "",
             "Outside trade calls recorded before the open with our model's odds, scored after expiry. "
             "Option prices are MODELED (no real quotes). 'Best (hindsight)' assumes a perfect exit and is not achievable in practice.", "",
             "## Recorded calls", "", "| ID | Recorded | Source | Contract | Spot | Needs | Our P(ITM) | P(touch) | Model premium | P(profit) | Note |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in calls.to_dict("records"):
        lines.append(f"| {c['id']} | {str(c['recorded_at'])[:16]} | {c['source']} | {c['symbol']} {c['strike']:g}{c['kind']} {c['expiry']} | "
                     f"{c['spot']} | {c['move_needed']:+.1%} | {c['p_itm']:.0%} | {c['p_touch']:.0%} | {c['model_premium']} | "
                     f"{c['p_profit']:.0%} | {c['note'] if isinstance(c['note'], str) else ''} |")
    if len(card):
        lines += ["", "## Scored", "", "| ID | Source | Contract | Expiry close | Result | Held to expiry | Best (hindsight) | Our P(ITM) |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in card.to_dict("records"):
            lines.append(f"| {r['id']} | {r['source']} | {r['symbol']} {r['contract']} | {r['expiry_close']} | "
                         f"{'ITM' if r['itm'] else 'worthless'} | {r['held_to_expiry_return']:+.0%} | {r['best_return_hindsight']:+.0%} | {r['model_p_itm']:.0%} |")
        lines += ["", "## By source", "", "| Source | Calls scored | Finished ITM | Avg our P(ITM) | Avg held-to-expiry return | Brier of our odds |",
                  "|---|---|---|---|---|---|"]
        for src, g in card.groupby("source"):
            lines.append(f"| {src} | {len(g)} | {g.itm.mean():.0%} | {g.model_p_itm.mean():.0%} | "
                         f"{g.held_to_expiry_return.mean():+.0%} | {g.brier_p_itm.mean():.3f} |")
        lines += ["", f"A source beats our model only if, over many calls, its calls finish in the money more often than our "
                      f"odds said (and pay for their premium). A handful of calls is anecdote, not evidence ({len(card)} scored so far)."]
    lines += _plans_report(folder)
    (folder / "REPORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-6:]) if len(card) else f"{len(calls)} calls recorded, none scored yet -> {folder / 'REPORT.md'}")


def _plans_report(folder):
    pp = folder / "plans.csv"
    if not pp.exists():
        return []
    plans = pd.read_csv(pp, keep_default_na=False)
    pc = folder / "plans_scorecard.csv"
    card = pd.read_csv(pc, keep_default_na=False) if pc.exists() else pd.DataFrame()
    pct = lambda v: f"{float(v):.0%}" if v != "" else ""  # noqa: E731
    out = ["", "## Stock plans", "",
           "Recorded before the open with our odds (zero-drift random paths at the stock's own volatility: what chance alone "
           "gives). Scored on real 1-minute bars: entry the minute after the trigger bar completes, stop first when a bar "
           "touches both, 0.05% cost each way. 'Best move' is hindsight, not an achievable exit.", "",
           "| ID | Recorded | Source | Plan | Spot | Risk / reward | Our P(trigger) | Once in: P(target first) | P(stop first) | Note |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for p in plans.to_dict("records"):
        trig = "at the open" if p["trigger"] == "none" else f"{p['tf']} {p['trigger'].replace('_', ' ')} {p['trigger_price']}"
        hold = "flat by the close" if int(p["hold_days"]) == 0 else f"hold ≤{p['hold_days']}d"
        out.append(f"| {p['id']} | {str(p['recorded_at'])[:16]} | {p['source']} | {p['side']} {p['symbol']} {trig} "
                   f"(within {p['trigger_days']}d), stop {p['stop']}, target {p['target']}, {hold} | {p['spot']} | "
                   f"{float(p['risk_pct']):.1%} / {float(p['reward_pct']):.1%} (R:R {p['stated_rr']}) | {pct(p['p_trigger'])} | "
                   f"{float(p['p_target']):.1%} | {pct(p['p_stop'])} | {p['note']} |")
    lp = folder / "plans_live.csv"
    live = pd.read_csv(lp, keep_default_na=False) if lp.exists() else pd.DataFrame()
    if len(live):
        out += ["", f"### Open plans (as of {live.as_of.max()} close; not a result until they finish)", "",
                "Marked to the last close, exit cost included. 'Worst so far' is the price furthest against the position since "
                "entry, and 'stop gap' how far that was from the stop.", "",
                "| ID | Source | Plan | Status | Entry | Last close | Open return | Worst so far | Stop gap | To target | Sessions left |",
                "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in live.to_dict("records"):
            o = r["status"] == "open"
            f = lambda k, fmt="{:+.2%}": fmt.format(float(r[k])) if o else ""  # noqa: E731
            left = f"{r['sessions_left']} to {'exit' if o else 'trigger'}"
            out.append(f"| {r['id']} | {r['source']} | {r['side']} {r['symbol']}, stop {r['stop']}, target {r['target']} | "
                       f"{r['status']}{(' (' + r['trigger_at'] + ')') if r['trigger_at'] else ''} | "
                       f"{(str(r['entry']) + ' (' + r['entry_time'] + ')') if o else ''} | {r['last_close']} | {f('open_ret')} | "
                       f"{(str(r['worst_price']) + ' (' + f('worst_ret') + ')') if o else ''} | {f('stop_gap_pct', '{:.2%}')} | "
                       f"{f('to_target_pct', '{:.1%}')} | {left} |")
    if len(card):
        out += ["", "### Scored plans", "", "| ID | Source | Plan | Result | Entry | Exit | Return | R | Best move (hindsight) | Our P(target) |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for r in card.to_dict("records"):
            trad = r["status"] != "not triggered"
            out.append(f"| {r['id']} | {r['source']} | {r['side']} {r['symbol']} | {r['status']} | "
                       f"{(str(r['entry']) + ' (' + r['entry_time'] + ')') if trad else ''} | "
                       f"{(str(r['exit']) + ' (' + r['exit_time'] + ')') if trad else ''} | "
                       f"{float(r['ret']):+.2%} | {r['r_multiple']} | {pct(r['best_move_hindsight'])} | {float(r['model_p_target']):.1%} |")
        out += ["", "| Source | Plans scored | Triggered | Hit target | Avg return per plan | Avg R when triggered |", "|---|---|---|---|---|---|"]
        for src, g in card.groupby("source"):
            t = g[g.status != "not triggered"]
            out.append(f"| {src} | {len(g)} | {len(t)} | {(t.status == 'target').sum()} | {g.ret.astype(float).mean():+.2%} | "
                       f"{(t.r_multiple.astype(float).mean() if len(t) else float('nan')):+.2f} |")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["add", "plan", "score", "report"])
    ap.add_argument("--side", choices=["long", "short"])
    ap.add_argument("--trigger", choices=["none", "close_below", "close_above"], default="none")
    ap.add_argument("--trigger-price", type=float); ap.add_argument("--tf", choices=["15m", "1h", "1d"], default="1h")
    ap.add_argument("--entry", type=float, help="the entry price as stated (informational; the real entry is replayed)")
    ap.add_argument("--stop", type=float); ap.add_argument("--target", type=float)
    ap.add_argument("--trigger-days", type=int, default=5, help="sessions the trigger may take, from the first session")
    ap.add_argument("--hold-days", type=int, default=20, help="sessions held after the entry session; 0 = flat by that close")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--source"); ap.add_argument("--symbol"); ap.add_argument("--strike", type=float)
    ap.add_argument("--kind", choices=["C", "P"]); ap.add_argument("--expiry"); ap.add_argument("--said", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--date", default=pd.Timestamp.now(tz=ET).strftime("%Y-%m-%d"))
    a = ap.parse_args()
    if a.cmd == "add":
        add(a.dir, a.source, a.symbol, a.strike, a.kind, a.expiry, a.said, a.note)
    elif a.cmd == "plan":
        plan_add(a.dir, a)
    elif a.cmd == "score":
        score(a.dir, a.date)
    else:
        report(a.dir)


if __name__ == "__main__":
    main()
