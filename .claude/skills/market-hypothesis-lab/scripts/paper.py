# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy", "yfinance>=0.2.40", "requests"]
# ///
"""Paper trading with realistic execution. No real orders are ever sent anywhere.

Each agent lives in <root>/agents/<name>/ with config.json (its pre-registered rules), AGENT.md,
state.json (cash), orders/, fills/, journal/ and equity.csv. Agents are ISOLATED: decide() reads only
the agent's own folder plus shared market data (prices, intraday bars, the champion forecast), except
agents in a TEAM ("team" in config.json), which trade the day together and share timestamped notes
(team_day; written to <root>/notes/<date>.csv). An optional "universe" list limits an agent to those
symbols. The comparison report shows each agent once it has `unlock_after_days` trading days.

Usage (root = e.g. lab/paper):
  uv run paper.py init    --root lab/paper --start 2026-10-19          # create agents with $1000 each
  uv run paper.py decide  --root lab/paper --agent bold    [--date D]  # before 09:30 ET
  uv run paper.py decide  --root lab/paper --agent careful [--date D]  # v1 only: 10:15-11:00 ET (v2 is replayed by execute)
  uv run paper.py decide  --root lab/paper --agent follower [--date D] # before 09:30 ET: outside calls (retired 2026-10-21)
  uv run paper.py decide  --root lab/paper --agent bold2   [--date D]  # before 09:30 ET: opening orders (rest replayed by execute)
  (agent "spreads": option debit spreads decided at 10:00 ET, replayed by execute with MODELED prices; no decide step)
  uv run paper.py checkpoint --root lab/paper2 [--date D]              # at each checkpoint time: every "checkpoints"
                                                                       # agent decides live (careful v3, hybrid)
  uv run paper.py execute --root lab/paper [--date D]                  # after the close: simulate fills
  uv run paper.py status  --root lab/paper --agent bold                # one agent's own stats only
  uv run paper.py compare --root lab/paper                             # each agent shown after 7 trading days

Realistic execution (market_rules.json in the root, pre-registered):
  - an order becomes active one minute after it is placed (latency); pre-open orders start at 09:30
  - market orders fill at the next bar's open, plus half the bid-ask spread and random adverse slippage;
    the spread is 3x wider in the first 5 minutes after the open
  - limit orders fill only if the price trades THROUGH the limit by at least 1 cent; a bar that only
    touches the limit fills with 30% probability (queue position), at the limit price
  - stop orders trigger when a bar trades at or through the stop, then fill like a market order at
    the worse of the stop and the bar's open (gaps fill worse), plus extra slippage
  - if a bar hits both the target and the stop, the stop is assumed first
  - every position is closed with a market order at 15:55 ET (no overnight risk)
  - cash account: buys use SETTLED cash only; sale proceeds settle the next business day (T+1)
  - fees: $0 commission; SEC fee and FINRA TAF on sales; fractional shares allowed (min order $1)
"""
import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, time as dtime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import cache  # noqa: E402

ET = "America/New_York"
DEFAULT_RULES = {
    "latency_min": 1, "half_spread_bps": {"default": 3.0}, "open_spread_mult": 3.0, "open_minutes": 5,
    "slippage_frac": 1.0, "stop_extra_slip_frac": 1.0, "touch_fill_prob": 0.3, "tick": 0.01,
    "sec_fee_per_dollar": 27.80e-6, "finra_taf_per_share": 0.000166, "finra_taf_max": 8.30,
    "close_out": "15:55", "min_order": 1.0, "unlock_after_days": 7,
    "opt_half_spread_pct": 0.04, "opt_min_half_spread": 0.02, "opt_open_spread_mult": 2.0, "opt_commission": 0.65,
    "fractional_contracts": True,
}


# ------------------------------------------------------------------ data
def intraday(symbol, date):
    """1-minute bars for one session (ET index), cached once the session is complete."""
    p = cache.path(f"intraday/{cache.safe(symbol)}/{date}.csv")
    now_et = pd.Timestamp.now(tz=ET)
    complete = pd.Timestamp(date).date() < now_et.date() or now_et.time() >= dtime(16, 30)
    if p.exists() and complete:
        return pd.read_csv(p, index_col=0, parse_dates=True)
    import yfinance as yf
    from polite import report_failure, report_success, wait
    wait("yahoo")
    d0 = pd.Timestamp(date)
    try:
        d = yf.Ticker(symbol).history(start=d0, end=d0 + pd.Timedelta(days=1), interval="1m", prepost=False)
    except Exception:
        report_failure("yahoo", 120)
        raise
    if d.empty:
        return d
    report_success("yahoo")
    d.index = d.index.tz_convert(ET).tz_localize(None)
    d = d[["Open", "High", "Low", "Close", "Volume"]]
    if complete:
        d.to_csv(p)
    return d


def champion_forecast(forecast_dir, date):
    p = Path(forecast_dir) / "predictions" / f"{date}.csv"
    if not p.exists():
        return None
    f = pd.read_csv(p)
    if "role" in f:
        f = f[f.role == "champion"]
    return f.set_index("symbol")


# ------------------------------------------------------------------ agent state (isolated)
class Agent:
    def __init__(self, root, name):
        self.root, self.name = Path(root), name
        self.dir = self.root / "agents" / name
        if not self.dir.exists():
            raise SystemExit(f"unknown agent {name}")
        self.cfg = json.loads((self.dir / "config.json").read_text())

    def state(self):
        return json.loads((self.dir / "state.json").read_text())

    def save(self, st):
        (self.dir / "state.json").write_text(json.dumps(st, indent=1))

    def path(self, *parts):
        p = self.dir.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


def settle(st, date):
    """Move proceeds whose settlement date has arrived into settled cash (T+1)."""
    keep = []
    for u in st["unsettled"]:
        if u["settles"] <= date:
            st["settled_cash"] += u["amount"]
        else:
            keep.append(u)
    st["unsettled"] = keep
    return st


def cents_down(x):
    """Round an order amount DOWN to whole cents, so orders sized to use all the cash never exceed it."""
    return math.floor(x * 100 + 1e-9) / 100


def next_bday(date):
    return str((pd.Timestamp(date) + pd.tseries.offsets.BDay(1)).date())


# ------------------------------------------------------------------ decisions (pre-registered rules)
def agent_forecast(cfg, fc):
    """The forecast rows this agent may trade: its "universe" list if it has one, else every forecast symbol."""
    if fc is None or not cfg.get("universe"):
        return fc
    return fc[fc.index.isin(cfg["universe"])]


def opening_orders(cfg, fc, settled_cash):
    """bold's pre-open rule: the top stocks by forecast `rank_by`, equal slices of settled cash, market orders at
    the open. With `open_positions`, it buys that many of its `max_positions` slices and keeps the rest for later."""
    n_open = cfg.get("open_positions", cfg["max_positions"])
    ranked = fc.sort_values(cfg["rank_by"], ascending=False).head(n_open)
    budget = settled_cash * cfg["invest_fraction"]
    slices = cfg["max_positions"] if "open_positions" in cfg else len(ranked)
    orders = []
    for sym, f in ranked.iterrows():
        amt = budget / slices
        if amt >= 1:
            orders.append({"symbol": sym, "side": "buy", "type": "market", "notional": cents_down(amt),
                           "target_pct": cfg["target_pct"], "stop_pct": cfg["stop_pct"],
                           "why": f"{cfg['rank_by']}={f[cfg['rank_by']]:.4f} (top {n_open})"})
    return orders


def exclusions(root, date):
    """Stocks no agent in this root may buy on `date`, from <root>/exclusions.csv (symbol, from, until, reason):
    takeover targets and other stocks whose price follows event news rather than our signals. Empty if no file."""
    p = Path(root) / "exclusions.csv"
    if not p.exists():
        return {}
    ex = pd.read_csv(p, dtype=str).fillna("")
    return {r["symbol"]: r["reason"] for _, r in ex.iterrows()
            if (r["from"] == "" or r["from"] <= date) and (r["until"] == "" or date <= r["until"])}


def apply_exclusions(root, date, fc, notes):
    ex = exclusions(root, date)
    hit = [s for s in fc.index if s in ex]
    if hit:
        notes.append("excluded today: " + "; ".join(f"{s} ({ex[s]})" for s in hit))
    return fc[~fc.index.isin(list(ex))]


def reaction_day_symbols(root, date):
    """Stocks whose earnings reaction day is `date`, from the morning's earnings_cal.py file (None if missing)."""
    p = Path(root) / "earnings" / f"{date}.json"
    return json.loads(p.read_text())["reaction_day"] if p.exists() else None


def momentum_check(w, f):
    """bold2's intraday rule on the bars `w` seen so far: up since the open and above yesterday's close.
    Strength = move since the open (the strongest goes first). No VWAP test of its own: that is careful's note."""
    o, last = w.Open.iloc[0], w.Close.iloc[-1]
    note = f"last {last:.2f} open {o:.2f} prev {f.prev_close:.2f} since open {last / o - 1:+.2%}"
    return last > o and last > f.prev_close, last / o - 1, last, note


def below_vwap(w):
    return w.Close.iloc[-1] < (w.Close * w.Volume).sum() / max(w.Volume.sum(), 1)


def entry_check(w, f, cfg):
    """careful's entry rule on the bars `w` seen so far today (all strictly before the decision minute)."""
    o, last = w.Open.iloc[0], w.Close.iloc[-1]
    vwap = (w.Close * w.Volume).sum() / max(w.Volume.sum(), 1)
    low_so_far, high_so_far = w.Low.min(), w.High.max()
    room = f.exp_range_pct - (high_so_far - low_so_far) / f.prev_close
    ok = last > o and last > vwap and last > f.prev_close and room >= cfg["min_room_pct"] \
        and f.p_touch_up1 >= cfg["min_p_touch_up1"]
    note = (f"last {last:.2f} open {o:.2f} vwap {vwap:.2f} prev {f.prev_close:.2f} "
            f"room {room:.2%} P(+1%) {f.p_touch_up1:.0%}")
    return ok, (last - vwap) / vwap, last, low_so_far, note


def confirm_check(w, f, cfg):
    """hybrid's entry test on the bars `w` seen so far: careful's trend confirmation without its 1%-target filters
    (price above today's open, above VWAP so far and above yesterday's close). Strength = the forecast `rank_by`
    (sigma: the biggest expected movers first, as bold ranks them)."""
    o, last = w.Open.iloc[0], w.Close.iloc[-1]
    vwap = (w.Close * w.Volume).sum() / max(w.Volume.sum(), 1)
    ok = last > o and last > vwap and last > f.prev_close
    note = f"last {last:.2f} open {o:.2f} vwap {vwap:.2f} prev {f.prev_close:.2f} {cfg['rank_by']} {f[cfg['rank_by']]:.4f}"
    return ok, float(f[cfg["rank_by"]]), last, w.Low.min(), note


def size_order(cfg, sym, last, low_so_far, equity, used, settled_cash):
    """Limit buy just above the last price; stop at max(low so far, -max_stop), but at least min_stop below
    the entry when min_stop_pct is set; risk-based size."""
    entry = last * (1 + cfg["entry_limit_offset"])
    stop = max(low_so_far, entry * (1 - cfg["max_stop_pct"]))
    if cfg.get("min_stop_pct"):
        stop = min(stop, entry * (1 - cfg["min_stop_pct"]))
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return None
    qty_risk = cfg["risk_per_trade"] * equity / risk_per_share
    amt = min(qty_risk * entry, cfg["max_position_frac"] * equity,
              cfg["max_total_frac"] * equity - used, settled_cash - used)
    if amt < 1:
        return None
    return {"symbol": sym, "side": "buy", "type": "limit", "limit": round(entry, 2), "notional": cents_down(amt),
            "target_pct": cfg["target_pct"], "stop_price": round(stop, 2)}


def decide(root, agent_name, date, forecast_dir, as_of=None):
    ag = Agent(root, agent_name)
    cfg = ag.cfg
    if cfg["decision"] == "watch_then_scan":
        print(f"{agent_name}: decides minute by minute; its decisions are replayed in the evening run "
              f"(bars before each decision minute only). Nothing to do now."); return
    if cfg["decision"] == "spreads_at_10":
        print(f"{agent_name}: decides at {cfg['decide_at']} ET on bars before then; replayed in the evening run "
              f"with MODELED option prices. Nothing to do now."); return
    if cfg["decision"] == "checkpoints":
        checkpoint(root, date, forecast_dir, as_of, only=[agent_name]); return
    if date < ag.state()["start"]:
        print(f"{agent_name}: starts on {ag.state()['start']}; nothing for {date}."); return
    out = ag.path("orders", f"{date}.json")
    if out.exists():
        print(f"{agent_name}: orders for {date} already placed; never re-placed."); return
    now = pd.Timestamp(f"{date} {as_of}", tz=ET) if as_of else pd.Timestamp.now(tz=ET)
    today = as_of is not None or now.strftime("%Y-%m-%d") == date
    st = settle(ag.state(), date)
    fc = agent_forecast(cfg, champion_forecast(forecast_dir, date))
    if fc is None and cfg["decision"] != "external_calls":
        print(f"{agent_name}: no forecast for {date}; no trading today."); return
    orders, notes = [], ([f"SIMULATED decision time {as_of} ET (test/replay, not a live decision)"] if as_of else [])
    equity = st.get("last_equity", st["settled_cash"] + sum(u["amount"] for u in st["unsettled"]))

    if cfg["decision"] == "external_calls":
        # follow outside calls recorded BEFORE this session's open (lab/external/calls.csv); never re-take a call
        if today and now.time() >= dtime(9, 30):
            notes.append(f"LATE: decided at {now.time():%H:%M} ET, after the open; orders start from now.")
        if cfg.get("retired_from") and date >= cfg["retired_from"]:
            out.write_text(json.dumps({"agent": agent_name, "date": date, "placed_at": now.isoformat(), "orders": [],
                                       "notes": [f"RETIRED from {cfg['retired_from']}: takes no new calls; "
                                                 "positions already held run to expiry"]}, indent=1))
            print(f"{agent_name}: retired from {cfg['retired_from']}; no new calls."); return
        cf = Path(cfg["calls_file"])
        calls = pd.read_csv(cf) if cf.exists() else pd.DataFrame(columns=["id"])
        taken = set(st.get("taken_calls", []))
        opened = pd.Timestamp(f"{date} 09:30", tz=ET)
        for c in calls.to_dict("records"):
            if c["id"] in taken or c["first_session"] != date:
                continue
            if pd.Timestamp(c["recorded_at"]).tz_convert(ET) >= opened:
                notes.append(f"{c['id']}: recorded after the open; skipped"); continue
            amt = cents_down(cfg["per_call_frac"] * equity)
            orders.append({"symbol": c["symbol"], "side": "buy", "type": "option_buy", "call_id": c["id"],
                           "kind": c["kind"], "strike": float(c["strike"]), "expiry": c["expiry"], "notional": amt,
                           "why": f"{c['source']}: {c['symbol']} {c['strike']:g}{c['kind']} {c['expiry']}"})
        if not orders:
            notes.append("no outside calls recorded for this session")
    elif cfg["decision"] in ("pre_open", "open_then_scan"):
        if today and now.time() >= dtime(9, 30):
            notes.append(f"LATE: decided at {now.time():%H:%M} ET, after the open; orders start from now.")
        fc = apply_exclusions(root, date, fc, notes)
        if cfg.get("skip_earnings_reaction_open"):  # E002 (lab/earnings): never buy at the open on a reaction day
            react = reaction_day_symbols(root, date)
            if react is None:
                notes.append("earnings calendar missing for today; no stock skipped (E002 rule could not be applied)")
            else:
                skipped = [s_ for s_ in fc.index if s_ in react]
                fc = fc[~fc.index.isin(react)]
                notes.append(f"earnings reaction day today: {', '.join(react) or 'none'}; "
                             + (f"left out of the opening ranking: {', '.join(skipped)} (E002)" if skipped else "none of my stocks"))
        orders = opening_orders(cfg, fc, st["settled_cash"])
        if cfg["decision"] == "open_then_scan":
            notes.append(f"opening orders only; from {cfg['decide_at']} ET the rest of the day is replayed minute by "
                         "minute in the evening run, with the team's shared notes")
    else:  # watch_then_trade
        h, m = map(int, cfg["decide_at"].split(":"))
        if today and now.time() < dtime(h, m):
            print(f"{agent_name}: too early ({now.time():%H:%M} ET); waits until {cfg['decide_at']} ET."); return
        lh, lm = map(int, cfg["latest"].split(":"))
        if today and now.time() > dtime(lh, lm):
            ag.path("orders", f"{date}.json").write_text(json.dumps(
                {"agent": agent_name, "date": date, "placed_at": now.isoformat(), "orders": [],
                 "notes": [f"MISSED: run at {now.time():%H:%M} ET, after the {cfg['latest']} cutoff; no trades."]}, indent=1))
            print(f"{agent_name}: missed the decision window; no trades today."); return
        cutoff = pd.Timestamp(f"{date} {cfg['decide_at']}")
        cands = []
        for sym, f in fc.iterrows():
            bars = intraday(sym, date)
            w = bars[bars.index < cutoff] if len(bars) else bars
            if len(w) < 30:
                notes.append(f"{sym}: not enough bars before {cfg['decide_at']} ({len(w)})"); continue
            ok, score_, last, or_low, note = entry_check(w, f, cfg)
            notes.append(f"{sym}: {note} -> {'candidate' if ok else 'skip'}")
            if ok:
                cands.append((sym, score_, last, or_low))
        cands.sort(key=lambda x: -x[1])
        used = 0.0
        for sym, score_, last, or_low in cands[: cfg["max_positions"]]:
            o = size_order(cfg, sym, last, or_low, equity, used, st["settled_cash"])
            if o:
                used += o["notional"]
                orders.append({**o, "why": f"above open/VWAP/prev close; strength {score_:+.2%}; stop at max(opening-range low, -{cfg['max_stop_pct']:.2%})"})
    rec = {"agent": agent_name, "date": date, "placed_at": now.isoformat(), "orders": orders, "notes": notes}
    out.write_text(json.dumps(rec, indent=1))
    print(f"{agent_name} {date}: {len(orders)} order(s) placed at {now.time():%H:%M:%S} ET")
    for o in orders:
        print("  ", {k: o[k] for k in o if k != "why"}, "-", o["why"])


# ------------------------------------------------------------------ execution simulator
class Sim:
    def __init__(self, rules, seed):
        self.R = rules
        self.rng = np.random.default_rng(seed)

    def half_spread(self, sym, t):
        bps = self.R["half_spread_bps"].get(sym, self.R["half_spread_bps"]["default"])
        if t.time() < (datetime.combine(t.date(), dtime(9, 30)) + pd.Timedelta(minutes=self.R["open_minutes"])).time():
            bps *= self.R["open_spread_mult"]
        return bps / 1e4

    def market(self, sym, side, bar_t, bar_open, extra=0.0):
        hs = self.half_spread(sym, bar_t)
        slip = self.rng.uniform(0, hs * self.R["slippage_frac"]) + extra * hs
        return bar_open * (1 + hs + slip) if side == "buy" else bar_open * (1 - hs - slip)

    def limit_hit(self, side, limit, bar):
        tick = self.R["tick"]
        if side == "buy":
            if bar.Low <= limit - tick:
                return min(limit, bar.Open)
            if bar.Low <= limit and self.rng.random() < self.R["touch_fill_prob"]:
                return limit
        else:
            if bar.High >= limit + tick:
                return max(limit, bar.Open)
            if bar.High >= limit and self.rng.random() < self.R["touch_fill_prob"]:
                return limit
        return None

    def sell_fees(self, qty, px):
        return qty * px * self.R["sec_fee_per_dollar"] + min(qty * self.R["finra_taf_per_share"], self.R["finra_taf_max"])


def simulate_order(sim, o, bars, active_from, close_out, expires=None):
    """Entry, then OCO target/stop, then the time exit. An unfilled entry is cancelled at `expires` (if given)."""
    sym = o["symbol"]
    b = bars[bars.index >= active_from]
    entry_px = entry_t = None
    for t, bar in b.iterrows():
        if t >= close_out or (expires is not None and t >= expires):
            break
        if o["type"] == "market":
            entry_px, entry_t = sim.market(sym, "buy", t, bar.Open), t
        else:
            px = sim.limit_hit("buy", o["limit"], bar)
            if px is not None:
                entry_px, entry_t = px, t
        if entry_px:
            break
    if entry_px is None:
        why = "limit never traded through" if o["type"] == "limit" else "no bars"
        if expires is not None:
            why += f"; cancelled at {expires:%H:%M}"
        return {"symbol": sym, "status": "not filled", "why": why}
    qty = o["notional"] / entry_px
    target = o.get("target_price") or entry_px * (1 + o["target_pct"])  # checkpoint orders fix it, like a broker bracket
    stop = o.get("stop_price") or entry_px * (1 - o["stop_pct"])
    exit_px = exit_t = reason = None
    for t, bar in b[b.index > entry_t].iterrows():
        if t >= close_out:
            exit_px, exit_t, reason = sim.market(sym, "sell", t, bar.Open), t, "time exit 15:55"
            break
        if bar.Low <= stop:  # stop first if both touched
            trig = min(stop, bar.Open)
            exit_px, exit_t, reason = sim.market(sym, "sell", t, trig, extra=sim.R["stop_extra_slip_frac"]), t, "stop"
            break
        px = sim.limit_hit("sell", target, bar)
        if px is not None:
            exit_px, exit_t, reason = px, t, "target"
            break
    if exit_px is None:  # data ended early: exit at last bar close
        t = b.index[-1]
        exit_px, exit_t, reason = sim.market(sym, "sell", t, b.Close.iloc[-1]), t, "time exit (last bar)"
    fees = sim.sell_fees(qty, exit_px)
    pnl = qty * (exit_px - entry_px) - fees
    return {"symbol": sym, "status": "filled", "qty": round(qty, 6), "entry_time": str(entry_t), "entry": round(entry_px, 4),
            "exit_time": str(exit_t), "exit": round(exit_px, 4), "reason": reason, "fees": round(fees, 4),
            "notional": o["notional"], "pnl": round(pnl, 4), "ret": pnl / o["notional"]}


# ------------------------------------------------------------------ options (MODELED prices; follower agent)
def daily_prices(symbol):
    """Path to cached daily bars, downloading politely if this machine (e.g. a fresh CI runner) lacks them."""
    p = cache.ROOT / f"prices/{cache.safe(symbol)}.csv"
    if p.exists():
        return p
    from fetch_data import get_prices
    return get_prices(symbol, quiet=True)


FALLBACK_RATE = 0.04


def risk_free_rate(date):
    """13-week T-bill (^IRX) known before `date`; a fixed fallback (logged) only if it can't be fetched."""
    try:
        irx = pd.read_csv(daily_prices("^IRX"), index_col=0, parse_dates=True).Close
        return float(irx[irx.index < pd.Timestamp(date)].iloc[-1]) / 100
    except Exception as e:  # rate barely moves short-dated option values; never crash the day over it
        print(f"WARNING: T-bill rate unavailable ({type(e).__name__}); using {FALLBACK_RATE:.2%}")
        return FALLBACK_RATE


def _opt_ctx(symbol, date, ctx):
    """Implied vol (options.py model) and rate known before `date`'s session."""
    key = (symbol, date)
    if key not in ctx:
        import options as op
        d = pd.read_csv(daily_prices(symbol), index_col=0, parse_dates=True)
        d = d[d.index < pd.Timestamp(date)]
        ctx[key] = (float(op.atm_iv_series(d).iloc[-1]), risk_free_rate(date))
    return ctx[key]


def opt_value(symbol, kind, K, expiry, S, t, date, ctx):
    import options as op
    iv, r = _opt_ctx(symbol, date, ctx)
    T = max((pd.Timestamp(f"{expiry} 16:00") - t).total_seconds() / (365 * 86400), 0.0)
    return op.bs(S, K, T, r, op.iv_at(iv, S, K), kind)


def opt_half_spread(sim, prem, t):
    hs = max(sim.R["opt_half_spread_pct"] * prem, sim.R["opt_min_half_spread"])
    if t.time() < (datetime.combine(t.date(), dtime(9, 30)) + pd.Timedelta(minutes=sim.R["open_minutes"])).time():
        hs *= sim.R["opt_open_spread_mult"]
    return hs


def session_closed(date):
    """True only if `date`'s regular session is over and actually traded (not a weekend/holiday)."""
    now = pd.Timestamp.now(tz=ET)
    if now < pd.Timestamp(f"{date} 16:15", tz=ET):
        print(f"REFUSED: the {date} session has not closed yet (now {now:%Y-%m-%d %H:%M} ET); nothing recorded.")
        return False
    if pd.Timestamp(date).weekday() >= 5:
        print(f"REFUSED: {date} is a weekend; nothing recorded."); return False
    spy = intraday("SPY", date)
    if spy is None or spy.empty:
        print(f"REFUSED: no trading on {date} (market holiday or data missing); nothing recorded.")
        return False
    return True


# ------------------------------------------------------------------ debit spreads (MODELED prices; "spreads" agent)
def next_week_friday(date):
    d = pd.Timestamp(date)
    return str((d + pd.Timedelta(days=(4 - d.weekday()) + 7)).date())


def spread_quote(sim, sym, sp, S, t, date, octx):
    """Mid of a vertical (long leg minus short leg, per share) and the half-spread paid on it. The spread trades as ONE
    limit order, so it pays about one leg's half-spread (the larger), not both: still wider than real quotes on liquid
    names, where a package often fills near its mid."""
    lo = opt_value(sym, sp["kind"], sp["long_strike"], sp["expiry"], S, t, date, octx)
    sh = opt_value(sym, sp["kind"], sp["short_strike"], sp["expiry"], S, t, date, octx)
    return lo - sh, max(opt_half_spread(sim, lo, t), opt_half_spread(sim, sh, t))


def manage_spread(sim, cfg, sp, bars, start_t, date, octx, close_out):
    """Walk one open spread through today's 1-minute bars from start_t. Each bar: the stop is checked first, on the
    spread's MID at the bar's worst price (Low for calls, High for puts), so trading costs alone can't trigger it; it
    sells at the bid there (gaps fill worse); then
    the resting target (a limit at entry x (1 + target_pct)) at the bar's best price; on `exit_by` it is sold at 15:55.
    Returns (exit dict or None, bid mark per share at the last bar)."""
    b = bars[(bars.index >= start_t) & (bars.index <= close_out)]
    stop_v, tgt_v = sp["entry_debit"] * (1 - cfg["stop_pct"]), sp["entry_debit"] * (1 + cfg["target_pct"])
    slip = lambda: 1 + sim.rng.uniform(0, sim.R["slippage_frac"])
    sym, call = sp["symbol"], sp["kind"] == "C"
    for t, bar in b.iterrows():
        if date >= sp["exit_by"] and t >= close_out:
            mid, hs = spread_quote(sim, sym, sp, bar.Open, t, date, octx)
            return {"t": t, "S": bar.Open, "px": max(mid - hs * slip(), 0.0), "reason": "time exit"}, None
        S = bar.Low if call else bar.High
        mid, hs = spread_quote(sim, sym, sp, S, t, date, octx)
        if mid <= stop_v:
            return {"t": t, "S": S, "px": max(mid - hs * slip(), 0.0), "reason": "stop"}, None
        S = bar.High if call else bar.Low
        mid, hs = spread_quote(sim, sym, sp, S, t, date, octx)
        if mid - hs >= tgt_v:
            return {"t": t, "S": S, "px": tgt_v, "reason": "target"}, None
    if b.empty:
        return None, sp.get("last_mark", sp["entry_debit"])
    t, S = b.index[-1], float(b.Close.iloc[-1])
    mid, hs = spread_quote(sim, sym, sp, S, t, date, octx)
    if date >= sp["exit_by"]:  # data ended before 15:55 on the last day: sell at the last bar
        return {"t": t, "S": S, "px": max(mid - hs, 0.0), "reason": "time exit (last bar)"}, None
    return None, max(mid - hs, 0.0)


def spread_day(root, ag, rules, fc, bars_cache, st, equity, date, close_out, octx, sim):
    """The "spreads" agent ("spreads_at_10"): manage open debit spreads minute by minute; at decide_at, using only bars
    before decide_at, open up to max_new new spreads on the top stocks by sigma that moved clearly one way in the first
    30 minutes (call spread if above both the open and yesterday's close, put spread if below both). Prices MODELED."""
    cfg = ag.cfg
    notes, fills, value = [], [], 0.0
    dh, dm = map(int, cfg["decide_at"].split(":"))
    decide_t = pd.Timestamp(f"{date} {dh:02d}:{dm:02d}")
    entry_t = decide_t + pd.Timedelta(minutes=rules["latency_min"])

    def bars_for(sym):
        if sym not in bars_cache:
            bars_cache[sym] = intraday(sym, date)
        return bars_cache[sym]

    def sold(sp, ex):
        proceeds = max(ex["px"] * sp["contracts"] * 100 - 2 * rules["opt_commission"] * sp["contracts"], 0.0)
        st["unsettled"].append({"amount": proceeds, "settles": next_bday(date)})
        fills.append({"symbol": sp["symbol"], "status": "spread sold", "contract": sp["label"], "exit_time": str(ex["t"]),
                      "stock": round(float(ex["S"]), 2), "exit": round(ex["px"], 3), "reason": ex["reason"],
                      "notional": sp["cost"], "pnl": round(proceeds - sp["cost"], 4), "ret": proceeds / sp["cost"] - 1})

    keep, busy_at_decision = [], 0
    for sp in st.get("spreads", []):
        bars = bars_for(sp["symbol"])
        if bars is None or bars.empty:
            keep.append(sp); value += sp.get("last_mark", sp["entry_debit"]) * sp["contracts"] * 100; busy_at_decision += 1; continue
        ex, mark = manage_spread(sim, cfg, sp, bars, pd.Timestamp(f"{date} 09:30"), date, octx, close_out)
        if ex:
            sold(sp, ex)
            busy_at_decision += ex["t"] >= decide_t
        else:
            sp["last_mark"] = mark; keep.append(sp); value += mark * sp["contracts"] * 100; busy_at_decision += 1
    st["spreads"] = keep

    slots = min(cfg["max_new"], cfg["max_open"] - busy_at_decision)
    cal = Path(root) / "earnings" / f"{date}.json"
    if fc is None:
        notes.append(f"no forecast for {date}; no new spreads")
        slots = 0
    elif not cal.exists():
        notes.append("earnings calendar missing; no new spreads (an earnings report inside the hold can't be ruled out)")
        slots = 0
    elif slots <= 0:
        notes.append(f"{busy_at_decision} spreads open at {cfg['decide_at']} (max {cfg['max_open']}); no new spreads")
    if slots > 0:
        exp = next_week_friday(date)
        last_before_exp = str((pd.Timestamp(exp) - pd.tseries.offsets.BDay(1)).date())
        exit_by = min(str((pd.Timestamp(date) + pd.tseries.offsets.BDay(cfg["max_hold_days"])).date()), last_before_exp,
                      cfg.get("close_all_on", "9999-12-31"))
        calj = json.loads(cal.read_text())
        reports, react, failed = calj.get("reports", {}), set(calj.get("reaction_day", [])), set(calj.get("failed", []))
        held = {sp["symbol"] for sp in st["spreads"]}
        budget_left = st["settled_cash"]
        for sym, f in fc.sort_values(cfg["rank_by"], ascending=False).iterrows():
            if slots <= 0:
                break
            if sym in held:
                notes.append(f"{sym}: already holding a spread"); continue
            if sym in react or sym in failed:
                notes.append(f"{sym}: " + ("earnings reaction day today" if sym in react else "earnings date lookup failed") + "; skipped")
                continue
            soon = [r for r in reports.get(sym, []) if pd.Timestamp(date, tz=ET) <= pd.Timestamp(r).tz_convert(ET)
                    <= pd.Timestamp(f"{exit_by} 16:00", tz=ET)]
            if soon:
                notes.append(f"{sym}: earnings {soon[0][:16]} on or before the exit day {exit_by}; skipped"); continue
            bars = bars_for(sym)
            w = bars[bars.index < decide_t] if bars is not None and len(bars) else None
            if w is None or len(w) < 20:
                notes.append(f"{sym}: not enough bars before {cfg['decide_at']}"); continue
            o, last = float(w.Open.iloc[0]), float(w.Close.iloc[-1])
            up, down = last > o and last > f.prev_close, last < o and last < f.prev_close
            note = f"{sym}: sigma {f.sigma:.3f}, {cfg['decide_at']} last {last:.2f} vs open {o:.2f} / prev close {f.prev_close:.2f}"
            if not (up or down):
                notes.append(note + " -> mixed; skip"); continue
            import options as op
            kind = "C" if up else "P"
            k1 = op.round_strike(last, last)
            k2 = op.round_strike(last * (1 + cfg["width_pct"] if up else 1 - cfg["width_pct"]), last)
            if k2 == k1:
                notes.append(note + " -> strikes collapse on the grid; skip"); continue
            b = bars[bars.index >= entry_t]
            if b.empty:
                notes.append(note + " -> no bars after the decision; skip"); continue
            t0, S0 = b.index[0], float(b.Open.iloc[0])
            sp = {"symbol": sym, "kind": kind, "long_strike": k1, "short_strike": k2, "expiry": exp, "exit_by": exit_by,
                  "label": f"{k1:g}/{k2:g}{kind} {exp}"}
            mid, hs = spread_quote(sim, sym, sp, S0, t0, date, octx)
            debit = mid + hs * (1 + sim.rng.uniform(0, rules["slippage_frac"]))
            if mid <= 0.05 or debit >= abs(k2 - k1):
                notes.append(note + f" -> modeled debit {debit:.2f} not tradable; skip"); continue
            amt = cents_down(min(cfg["risk_per_spread"] * equity, budget_left))
            if amt < rules["min_order"]:
                notes.append(note + " -> no settled cash left; skip"); continue
            one = debit * 100 + 2 * rules["opt_commission"]
            sp.update({"contracts": amt / one, "entry_debit": debit, "cost": amt, "entry_time": str(t0), "stock_at_entry": S0})
            budget_left -= amt
            st["settled_cash"] -= amt
            fills.append({"symbol": sym, "status": "spread bought", "contract": sp["label"], "entry_time": str(t0),
                          "stock": round(S0, 2), "model_mid": round(mid, 3), "entry": round(debit, 3),
                          "contracts": round(sp["contracts"], 5), "notional": amt, "exit_by": exit_by,
                          "real_account_note": f"a real account needs ${one:.0f} for 1 spread (max loss ${one:.0f})"})
            notes.append(note + f" -> {'CALL' if up else 'PUT'} debit spread {sp['label']}")
            ex, mark = manage_spread(sim, cfg, sp, bars, t0 + pd.Timedelta(minutes=1), date, octx, close_out)
            if ex:
                sold(sp, ex)
            else:
                sp["last_mark"] = mark; st["spreads"].append(sp); value += mark * sp["contracts"] * 100
            held.add(sym); slots -= 1
    return {"orders": [], "notes": notes, "placed_at": None}, fills, value


def scan_day(ag, rules, fc, bars_cache, equity, settled_cash, date, close_out):
    """careful v2 ("watch_then_scan"): from decide_at to last_entry, re-check the entry rule EVERY minute
    using only bars that ended before that minute. A limit order goes live one minute later (latency) and is
    cancelled if unfilled after limit_ttl_min. At most max_positions orders filled or live in a day (a filled
    order keeps its slot even after it exits), one fill per stock. Each order has its own random seed, so a
    decision at minute t never depends on anything after t (checked by tests: truncating the bars at t
    leaves every decision up to t unchanged)."""
    cfg = ag.cfg
    t = pd.Timestamp(f"{date} {cfg['decide_at']}")
    last_entry = pd.Timestamp(f"{date} {cfg['last_entry']}")
    ttl = pd.Timedelta(minutes=cfg["limit_ttl_min"])
    lat = pd.Timedelta(minutes=rules["latency_min"])
    bars = {}
    for sym in fc.index:
        if sym not in bars_cache:
            bars_cache[sym] = intraday(sym, date)
        if bars_cache[sym] is not None and len(bars_cache[sym]):
            bars[sym] = bars_cache[sym]
    placed, notes, first_ok = [], [], {}
    while t <= last_entry:
        # what the agent knows at t: a filled order keeps its slot; an unfilled one until it is cancelled
        live = [(o, f) for o, f in placed if f["status"] == "filled" or o["_expires"] > t]
        if len(live) < cfg["max_positions"]:
            busy = {o["symbol"] for o, _ in live}
            cands = []
            for sym, f in fc.iterrows():
                if sym in busy or sym not in bars:
                    continue
                w = bars[sym][bars[sym].index < t]
                if len(w) < 30:
                    continue
                ok, strength, last, low_so_far, note = entry_check(w, f, cfg)
                if t == pd.Timestamp(f"{date} {cfg['decide_at']}"):
                    notes.append(f"{t:%H:%M} {sym}: {note} -> {'candidate' if ok else 'skip'}")
                if ok:
                    first_ok.setdefault(sym, t)
                    cands.append((strength, sym, last, low_so_far))
            used = sum(o["notional"] for o, _ in live)
            for strength, sym, last, low_so_far in sorted(cands, reverse=True)[: cfg["max_positions"] - len(live)]:
                o = size_order(cfg, sym, last, low_so_far, equity, used, settled_cash)
                if not o:
                    continue
                o.update({"placed_at": str(t), "_expires": t + lat + ttl,
                          "why": f"{t:%H:%M}: above open/VWAP/prev close; strength {strength:+.2%}; "
                                 f"stop at max(low so far, -{cfg['max_stop_pct']:.2%})"})
                seed = int(hashlib.sha256(f"{date}|{ag.name}|{sym}|{t}".encode()).hexdigest()[:8], 16)
                fill = simulate_order(Sim(rules, seed), o, bars[sym], t + lat, close_out, expires=o["_expires"])
                fill["placed_at"] = str(t)
                placed.append((o, fill))
                used += o["notional"]
        t += pd.Timedelta(minutes=1)
    notes.append(f"scanned every minute {cfg['decide_at']}-{cfg['last_entry']} ET; "
                 + (", ".join(f"{s} first qualified {v:%H:%M}" for s, v in first_ok.items()) or "no stock ever qualified"))
    orders = [{k: v for k, v in o.items() if not k.startswith("_")} | {"cancel_at": str(o["_expires"])} for o, _ in placed]
    rec = {"agent": ag.name, "date": date, "placed_at": None, "decision": "watch_then_scan (replayed minute by minute)",
           "orders": orders, "notes": notes}
    return rec, [f for _, f in placed]


def _holds(o, f, t):
    """At minute t, does this order still use a slot? A fill holds it until a target or stop the agent has seen
    (exit bar before t); a "time exit (last bar)" only means the data ended, so nothing is known. An unfilled
    order holds it until it is cancelled."""
    if f["status"] == "filled":
        return not (f["reason"] in ("target", "stop") and pd.Timestamp(f["exit_time"]) < t)
    return o["_expires"] > t


def team_day(members, rules, fc, bars_cache, date, close_out):
    """Agents in a team trade the day together, replayed minute by minute from bars that ended before each minute,
    and SHARE NOTES: every buy, target and stop is posted one minute after the bar it happened in, and an agent at
    minute t reads only notes posted at or before t. Both skip a stock either one was stopped out of in the last
    `avoid_after_stop_min` minutes; with `heed_partner_weak`, an agent also skips a stock the partner's view (the
    bars before the previous minute) shows below VWAP. A slot frees when its position exits, but cash spent today
    stays spent until it settles (T+1), so settled cash is what limits trades later in the day. Opening orders
    placed in the morning (open_then_scan) are filled first. Each order has its own random seed, so decisions up
    to minute t never depend on bars after t (check_scan_lookahead.py --team).
    members: list of {"ag", "equity", "settled_cash", "opening" (the morning orders record or None)}.
    Returns ({agent name: (orders record, fills)}, shared notes [(known_at, author, symbol, text, kind)])."""
    lat, minute = pd.Timedelta(minutes=rules["latency_min"]), pd.Timedelta(minutes=1)
    open_t = pd.Timestamp(f"{date} 09:30")
    for sym in fc.index:
        if sym not in bars_cache:
            bars_cache[sym] = intraday(sym, date)
    bars = {s: b for s, b in bars_cache.items() if s in fc.index and b is not None and len(b)}
    posted = []

    def post(name, f):
        if f["status"] != "filled":
            return
        posted.append((pd.Timestamp(f["entry_time"]) + minute, name, f["symbol"], f"bought @ {f['entry']:.2f}", "buy"))
        if f["reason"] in ("target", "stop"):
            posted.append((pd.Timestamp(f["exit_time"]) + minute, name, f["symbol"],
                           f"{f['reason']} @ {f['exit']:.2f}", f["reason"]))

    for m in members:
        ag, cfg = m["ag"], m["ag"].cfg
        m.update(placed=[], notes=[], first_ok={}, said=set(), fc=agent_forecast(cfg, fc),
                 start=pd.Timestamp(f"{date} {cfg['decide_at']}"), end=pd.Timestamp(f"{date} {cfg['last_entry']}"))
        op = m["opening"]
        if op and op.get("orders"):
            placed_t = pd.Timestamp(op["placed_at"]).tz_convert(ET).tz_localize(None)
            active = max(open_t, placed_t + lat)
            sim = Sim(rules, int(hashlib.sha256(f"{date}|{ag.name}".encode()).hexdigest()[:8], 16))
            spent = 0.0
            for o in op["orders"]:
                if o["notional"] > m["settled_cash"] - spent + 1e-9 or o["notional"] < rules["min_order"]:
                    fill = {"symbol": o["symbol"], "status": "rejected", "why": "insufficient settled cash"}
                elif o["symbol"] not in bars:
                    fill = {"symbol": o["symbol"], "status": "not filled", "why": "no intraday data"}
                else:
                    fill = simulate_order(sim, o, bars[o["symbol"]], active, close_out)
                spent += o["notional"] if fill["status"] == "filled" else 0.0
                m["placed"].append(({**o, "_expires": close_out if fill["status"] == "filled" else active}, fill))
                post(ag.name, fill)

    def say(m, key, text):  # each kind of skip is written to the journal once a day
        if key not in m["said"]:
            m["said"].add(key); m["notes"].append(text)

    t = min(m["start"] for m in members)
    while t <= max(m["end"] for m in members):
        visible = [n for n in posted if n[0] <= t]
        for m in members:
            ag, cfg, placed = m["ag"], m["ag"].cfg, m["placed"]
            if not m["start"] <= t <= m["end"]:
                continue
            live = [(o, f) for o, f in placed if _holds(o, f, t)]
            if len(live) >= cfg["max_positions"]:
                continue
            used = sum(o["notional"] for o, f in placed if f["status"] == "filled" or o["_expires"] > t)
            busy = {o["symbol"] for o, _ in live}
            bought = {f["symbol"] for _, f in placed if f["status"] == "filled" and pd.Timestamp(f["entry_time"]) < t}
            avoid = pd.Timedelta(minutes=cfg["avoid_after_stop_min"])
            stopped = {n[2]: n for n in visible if n[4] == "stop" and t - n[0] < avoid}
            partners = [x for x in members if x is not m]
            cands = []
            for sym, f in m["fc"].iterrows():
                if sym in busy or sym in bought or sym not in bars:
                    continue
                w = bars[sym][bars[sym].index < t]
                if len(w) < cfg["min_bars"]:
                    continue
                if cfg["entry_rule"] == "momentum":
                    ok, strength, last, note = momentum_check(w, f); low = None
                else:
                    ok, strength, last, low, note = entry_check(w, f, cfg)
                if t == m["start"]:
                    m["notes"].append(f"{t:%H:%M} {sym}: {note} -> {'candidate' if ok else 'skip'}")
                if not ok:
                    continue
                if sym in stopped:
                    k, who = stopped[sym][0], stopped[sym][1]
                    say(m, f"stop|{sym}|{k}", f"{t:%H:%M} {sym}: qualified but skipped: {who} was stopped out of it "
                                              f"at {k - minute:%H:%M} (shared note; avoided for {cfg['avoid_after_stop_min']} min)")
                    continue
                weak = [x["ag"].name for x in partners if cfg.get("heed_partner_weak") and sym in x["fc"].index
                        and len(pw := bars[sym][bars[sym].index < t - minute]) and below_vwap(pw)]
                if weak:
                    say(m, f"weak|{sym}", f"{t:%H:%M} {sym}: qualified but skipped: {weak[0]} marks it below VWAP "
                                          "(shared note; later skips of this stock for the same reason not listed)")
                    continue
                m["first_ok"].setdefault(sym, t)
                cands.append((strength, sym, last, low))
            for strength, sym, last, low in sorted(cands, reverse=True)[: cfg["max_positions"] - len(live)]:
                if cfg["entry_rule"] == "momentum":
                    amt = cents_down(min(m["settled_cash"] - used,
                                         m["settled_cash"] * cfg["invest_fraction"] / cfg["max_positions"]))
                    if amt < rules["min_order"]:
                        say(m, "cash", f"{t:%H:%M}: {sym} qualified but no settled cash left today (T+1)")
                        continue
                    o = {"symbol": sym, "side": "buy", "type": "limit", "limit": round(last * (1 + cfg["entry_limit_offset"]), 2),
                         "notional": amt, "target_pct": cfg["target_pct"], "stop_pct": cfg["stop_pct"]}
                    why = (f"{t:%H:%M}: up {strength:+.2%} since the open and above yesterday's close; "
                           f"target/stop ±{cfg['target_pct']:.1%}")
                else:
                    o = size_order(cfg, sym, last, low, m["equity"], used, m["settled_cash"])
                    if not o:
                        say(m, "cash", f"{t:%H:%M}: {sym} qualified but no cash left within its limits today")
                        continue
                    why = (f"{t:%H:%M}: above open/VWAP/prev close; strength {strength:+.2%}; "
                           f"stop at max(low so far, -{cfg['max_stop_pct']:.2%})")
                o.update({"placed_at": str(t), "_expires": t + lat + pd.Timedelta(minutes=cfg["limit_ttl_min"]), "why": why})
                seed = int(hashlib.sha256(f"{date}|{ag.name}|{sym}|{t}".encode()).hexdigest()[:8], 16)
                fill = simulate_order(Sim(rules, seed), o, bars[sym], t + lat, close_out, expires=o["_expires"])
                fill["placed_at"] = str(t)
                placed.append((o, fill))
                used += o["notional"]
                post(ag.name, fill)
        t += minute
    out = {}
    for m in members:
        cfg, op = m["ag"].cfg, m["opening"]
        m["notes"].append(f"scanned every minute {cfg['decide_at']}-{cfg['last_entry']} ET with shared notes; "
                          + (", ".join(f"{s} first qualified {v:%H:%M}" for s, v in m["first_ok"].items())
                             or "no stock ever qualified"))
        orders = [{k: v for k, v in o.items() if not k.startswith("_")}
                  | ({"cancel_at": str(o["_expires"])} if "placed_at" in o else {}) for o, _ in m["placed"]]
        rec = {"agent": m["ag"].name, "date": date, "placed_at": op["placed_at"] if op else None,
               "decision": f"{cfg['decision']} (team, replayed minute by minute)", "opening": op,
               "orders": orders, "notes": (op or {}).get("notes", []) + m["notes"]}
        out[m["ag"].name] = (rec, [f for _, f in m["placed"]])
    return out, posted


# ------------------------------------------------------------------ checkpoint agents (season 2: careful v3, hybrid)
def cp_orders(rec):
    return [o for r in rec.get("rounds", []) for o in r["orders"]]


def cp_fill(rules, name, date, o, bars, close_out, until=None):
    """Simulate one checkpoint order. With `until`, only bars before it are used: what the agent can know then.
    The seed depends only on the order, and the simulator walks bars in order, so the status known at `until`
    is the same as in the full-day replay."""
    t = pd.Timestamp(o["decision_minute"])
    b = bars if until is None or bars is None or not len(bars) else bars[bars.index < until]
    if b is None or not len(b):
        return {"symbol": o["symbol"], "status": "not filled", "why": "no intraday data", "placed_at": str(t)}
    seed = int(hashlib.sha256(f"{date}|{name}|{o['symbol']}|{t}".encode()).hexdigest()[:8], 16)
    f = simulate_order(Sim(rules, seed), o, b, t + pd.Timedelta(minutes=rules["latency_min"]), close_out,
                       expires=pd.Timestamp(o["cancel_at"]))
    f["placed_at"] = str(t)
    return f


def checkpoint(root, date, forecast_dir, as_of=None, only=None):
    """Live decisions for "checkpoints" agents, run at each checkpoint time (cron-job.org timers). Each agent
    decides on 1-minute bars that ended before the current minute, then writes a limit buy with a fixed target
    and stop (the same prices the broker mirror sends as a bracket order). An order not filled by the next
    checkpoint is cancelled there (or at 15:55 after the last one). A run more than `grace_min` minutes after
    its checkpoint decides nothing, so a late GitHub run can never trade on a view the agent could not have had.
    Slots: at most `max_orders_per_day` FILLED orders a day (a filled order keeps its slot after it exits), one
    per stock; cash spent today stays spent until it settles (T+1)."""
    root = Path(root)
    rules = {**DEFAULT_RULES, **json.loads((root / "market_rules.json").read_text())}
    now = pd.Timestamp(f"{date} {as_of}", tz=ET) if as_of else pd.Timestamp.now(tz=ET)
    if not as_of and now.strftime("%Y-%m-%d") != date:
        print(f"checkpoint: {date} is not today in New York; nothing decided"); return
    t = now.tz_localize(None).floor("min")
    ch, cm = map(int, rules["close_out"].split(":"))
    close_out = pd.Timestamp(f"{date} {ch:02d}:{cm:02d}")
    fc_all = champion_forecast(forecast_dir, date)
    bars_cache = {}

    def bars_for(sym):
        if sym not in bars_cache:
            bars_cache[sym] = intraday(sym, date)
        return bars_cache[sym]

    names = only or sorted(p.name for p in (root / "agents").iterdir() if (p / "config.json").exists())
    for name in names:
        ag = Agent(root, name)
        cfg = ag.cfg
        if cfg.get("decision") != "checkpoints" or not (ag.dir / "state.json").exists():
            continue
        if date < ag.state()["start"]:
            print(f"{name}: starts on {ag.state()['start']}; nothing for {date}."); continue
        cps = [pd.Timestamp(f"{date} {c}") for c in cfg["checkpoints"]]
        due = [c for c in cps if c <= t]
        if not due:
            print(f"{name}: {t:%H:%M} ET is before the first checkpoint {cfg['checkpoints'][0]}; nothing decided"); continue
        c = due[-1]
        if t - c > pd.Timedelta(minutes=cfg.get("grace_min", 20)):
            print(f"{name}: {t:%H:%M} ET is more than {cfg.get('grace_min', 20)} min after the {c:%H:%M} checkpoint; "
                  "nothing decided (too late)"); continue
        of = ag.path("orders", f"{date}.json")
        rec = json.loads(of.read_text()) if of.exists() else {"agent": name, "date": date, "decision": "checkpoints",
                                                              "rounds": []}
        if any(r["checkpoint"] == f"{c:%H:%M}" for r in rec["rounds"]):
            print(f"{name}: the {c:%H:%M} checkpoint was already decided; never re-decided."); continue
        notes = [f"SIMULATED decision time {as_of} ET (test/replay, not a live decision)"] if as_of else []
        orders = []
        if fc_all is None:
            notes.append(f"no forecast for {date}; no trading today")
        else:
            fc = apply_exclusions(root, date, agent_forecast(cfg, fc_all), notes)
            st = settle(ag.state(), date)
            equity = st.get("last_equity", st["settled_cash"] + sum(u["amount"] for u in st["unsettled"]))
            later = [x for x in cps if x > c]
            cancel_at = later[0] if later else close_out
            filled, used = [], 0.0
            for o in cp_orders(rec):  # what is known now about earlier orders (bars before this minute only)
                f = cp_fill(rules, name, date, o, bars_for(o["symbol"]), close_out, until=t)
                if f["status"] == "filled":
                    filled.append(o["symbol"]); used += o["notional"]
            slots = cfg["max_orders_per_day"] - len(filled)
            if slots <= 0:
                notes.append(f"{t:%H:%M}: all {cfg['max_orders_per_day']} trades for today used ({', '.join(filled)})")
            else:
                check = entry_check if cfg["entry_rule"] == "careful" else confirm_check
                cands = []
                for sym, f in fc.iterrows():
                    if sym in filled:
                        continue
                    b = bars_for(sym)
                    w = b[b.index < t] if b is not None and len(b) else b
                    if w is None or len(w) < cfg.get("min_bars", 30):
                        notes.append(f"{t:%H:%M} {sym}: not enough bars ({0 if w is None else len(w)})"); continue
                    ok, strength, last, low, note = check(w, f, cfg)
                    notes.append(f"{t:%H:%M} {sym}: {note} -> {'candidate' if ok else 'skip'}")
                    if ok:
                        cands.append((strength, sym, last, low))
                for strength, sym, last, low in sorted(cands, reverse=True)[:slots]:
                    o = size_order(cfg, sym, last, low, equity, used, st["settled_cash"])
                    if not o:
                        notes.append(f"{t:%H:%M} {sym}: qualified but no cash left within its limits"); continue
                    o.update(target_price=round(o["limit"] * (1 + cfg["target_pct"]), 2), placed_at=now.isoformat(),
                             decision_minute=str(t), cancel_at=str(cancel_at),
                             why=(f"{c:%H:%M} checkpoint: above open/VWAP/prev close; strength {strength:.4f}; "
                                  f"target {cfg['target_pct']:+.1%} from the limit; stop {o['stop_price']}"))
                    used += o["notional"]
                    orders.append(o)
        rec["rounds"].append({"checkpoint": f"{c:%H:%M}", "decided_at": now.isoformat(), "orders": orders, "notes": notes})
        of.write_text(json.dumps(rec, indent=1))
        print(f"{name} {date} {c:%H:%M} checkpoint (decided {now:%H:%M:%S} ET): {len(orders)} order(s)")
        for o in orders:
            print(f"   BUY {o['symbol']} limit {o['limit']} ${o['notional']:.2f}, target {o['target_price']}, "
                  f"stop {o['stop_price']}, cancel at {o['cancel_at'][11:16]}")


def execute(root, date, forecast_dir="lab/forecast"):
    if not session_closed(date):
        return
    root = Path(root)
    rules = {**DEFAULT_RULES, **json.loads((root / "market_rules.json").read_text())}
    ch, cm = map(int, rules["close_out"].split(":"))
    close_out = pd.Timestamp(f"{date} {ch:02d}:{cm:02d}")
    bars_cache = {}
    # team agents trade the day together, so they are replayed first, side by side
    members = []
    for adir in sorted((root / "agents").iterdir()):
        if (adir / "config.json").exists() and (adir / "state.json").exists() and not (adir / "fills" / f"{date}.csv").exists():
            ag = Agent(root, adir.name)
            if not ag.cfg.get("team") or date < ag.state()["start"]:
                continue
            st = settle(ag.state(), date)
            of = ag.dir / "orders" / f"{date}.json"
            opening = None
            if ag.cfg["decision"] == "open_then_scan" and of.exists():
                rec = json.loads(of.read_text())
                opening = rec.get("opening", rec) if "decision" in rec else rec  # a re-run reads the morning record
            members.append({"ag": ag, "settled_cash": st["settled_cash"], "opening": opening,
                            "equity": st.get("last_equity", st["settled_cash"] + sum(u["amount"] for u in st["unsettled"]))})
    team_out = {}
    if members:
        fc = champion_forecast(forecast_dir, date)
        if fc is None:
            team_out = {m["ag"].name: ({"orders": [], "notes": [f"no forecast for {date}; no trading today"]}, []) for m in members}
        else:
            team_out, posted = team_day(members, rules, fc, bars_cache, date, close_out)
            nf = root / "notes" / f"{date}.csv"
            nf.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame([{"known_at": str(k), "author": a, "symbol": sym, "note": txt} for k, a, sym, txt, _ in sorted(posted)],
                         columns=["known_at", "author", "symbol", "note"]).to_csv(nf, index=False)
    for adir in sorted((root / "agents").iterdir()):
        if not (adir / "config.json").exists() or not (adir / "state.json").exists():
            print(f"{adir.name}: no config.json/state.json; skipped (not a configured agent)"); continue
        ag = Agent(root, adir.name)
        if date < ag.state()["start"]:  # e.g. a late re-run of the day before a new agent's first day
            print(f"{ag.name}: starts on {ag.state()['start']}; {date} not processed."); continue
        of = ag.dir / "orders" / f"{date}.json"
        ff = ag.path("fills", f"{date}.csv")
        if ff.exists():
            print(f"{ag.name}: {date} already executed."); continue
        st = settle(ag.state(), date)
        st.setdefault("positions", [])
        start_equity = st.get("last_equity", st["settled_cash"] + sum(u["amount"] for u in st["unsettled"]))
        octx = {}
        teamed = ag.name in team_out
        spreads = ag.cfg["decision"] == "spreads_at_10"
        cpoint = ag.cfg["decision"] == "checkpoints"
        scanning = teamed or spreads or cpoint or ag.cfg["decision"] == "watch_then_scan"
        seed = int(hashlib.sha256(f"{date}|{ag.name}".encode()).hexdigest()[:8], 16)
        sim = Sim(rules, seed)
        spread_value = 0.0
        if spreads:
            fc = agent_forecast(ag.cfg, champion_forecast(forecast_dir, date))
            rec, scan_fills, spread_value = spread_day(root, ag, rules, fc, bars_cache, st, start_equity, date, close_out, octx, sim)
            of.parent.mkdir(parents=True, exist_ok=True)
            of.write_text(json.dumps(rec, indent=1))
        elif teamed:
            rec, scan_fills = team_out[ag.name]
            of.parent.mkdir(parents=True, exist_ok=True)
            of.write_text(json.dumps(rec, indent=1))
        elif cpoint:  # the live checkpoint decisions are simulated as placed; the record itself is never rewritten
            live = json.loads(of.read_text()) if of.exists() else {"rounds": []}
            scan_fills, spent = [], 0.0
            for o in cp_orders(live):
                if o["notional"] > st["settled_cash"] - spent + 1e-9 or o["notional"] < rules["min_order"]:
                    scan_fills.append({"symbol": o["symbol"], "status": "rejected", "why": "insufficient settled cash",
                                       "placed_at": o["decision_minute"]}); continue
                if o["symbol"] not in bars_cache:
                    bars_cache[o["symbol"]] = intraday(o["symbol"], date)
                f = cp_fill(rules, ag.name, date, o, bars_cache[o["symbol"]], close_out)
                spent += o["notional"] if f["status"] == "filled" else 0.0
                scan_fills.append(f)
            rounds = live.get("rounds", [])
            notes = [f"{r['checkpoint']} checkpoint, decided {r['decided_at'][11:19]} ET: "
                     + (", ".join(f"{o['symbol']} limit {o['limit']}" for o in r["orders"]) or "no order") for r in rounds]
            for r in rounds:
                notes += [n for n in r["notes"] if not n.endswith("-> skip")]
            missing = [c for c in ag.cfg["checkpoints"] if c not in {r["checkpoint"] for r in rounds}]
            if missing:
                notes.append("checkpoints that did not run (no decision): " + ", ".join(missing))
            rec = {"orders": cp_orders(live), "notes": notes}
        elif scanning:
            fc = agent_forecast(ag.cfg, champion_forecast(forecast_dir, date))
            if fc is None:
                rec, scan_fills = {"orders": [], "notes": [f"no forecast for {date}; no trading today"]}, []
            else:
                rec, scan_fills = scan_day(ag, rules, fc, bars_cache, start_equity, st["settled_cash"], date, close_out)
            of.parent.mkdir(parents=True, exist_ok=True)
            of.write_text(json.dumps(rec, indent=1))
        else:
            rec = json.loads(of.read_text()) if of.exists() else {"orders": [], "notes": ["no orders file (did not run)"]}
        placed = pd.Timestamp(rec["placed_at"]).tz_convert(ET).tz_localize(None) if rec.get("placed_at") else None
        open_t = pd.Timestamp(f"{date} 09:30")
        active_from = max(open_t, placed + pd.Timedelta(minutes=rules["latency_min"])) if placed is not None else open_t
        fills, spent = (scan_fills, 0.0) if scanning else ([], 0.0)
        for o in ([] if scanning else rec["orders"]):
            if o["notional"] > st["settled_cash"] - spent + 1e-9 or o["notional"] < rules["min_order"]:
                fills.append({"symbol": o["symbol"], "status": "rejected", "why": "insufficient settled cash"}); continue
            if o["symbol"] not in bars_cache:
                bars_cache[o["symbol"]] = intraday(o["symbol"], date)
            bars = bars_cache[o["symbol"]]
            if bars is None or bars.empty:
                fills.append({"symbol": o["symbol"], "status": "not filled", "why": "no intraday data"}); continue
            if o["type"] == "option_buy":
                b = bars[bars.index >= active_from]
                if b.empty:
                    fills.append({"symbol": o["symbol"], "status": "not filled", "why": "no bars after order time"}); continue
                t0, S0 = b.index[0], float(b.Open.iloc[0])
                mid = opt_value(o["symbol"], o["kind"], o["strike"], o["expiry"], S0, t0, date, octx)
                ask = mid + opt_half_spread(sim, mid, t0) * (1 + sim.rng.uniform(0, rules["slippage_frac"]))
                comm_per_contract = rules["opt_commission"]
                contracts = (o["notional"] - 0) / (ask * 100 + comm_per_contract)
                one = ask * 100 + comm_per_contract
                if not rules["fractional_contracts"] and contracts < 1:
                    fills.append({"symbol": o["symbol"], "status": "rejected", "call_id": o["call_id"],
                                  "why": f"1 contract costs ${one:.0f} > ${o['notional']:.0f} cap (no fractional contracts)"}); continue
                st["positions"].append({"call_id": o["call_id"], "symbol": o["symbol"], "kind": o["kind"], "strike": o["strike"],
                                        "expiry": o["expiry"], "contracts": contracts, "entry_price": ask, "cost": o["notional"],
                                        "entry_time": str(t0), "stock_at_entry": S0})
                st.setdefault("taken_calls", []).append(o["call_id"])
                st["settled_cash"] -= o["notional"]
                fills.append({"symbol": o["symbol"], "status": "option bought", "call_id": o["call_id"],
                              "contract": f"{o['strike']:g}{o['kind']} {o['expiry']}", "entry_time": str(t0), "stock": round(S0, 2),
                              "model_mid": round(mid, 3), "entry": round(ask, 3), "contracts": round(contracts, 5),
                              "notional": o["notional"], "real_account_note": (f"a real account needs ${one:.0f} for 1 contract"
                                                                               if contracts < 1 else "")})
                spent += o["notional"]
                continue
            f = simulate_order(sim, o, bars, active_from, close_out)
            if f["status"] == "filled":
                spent += o["notional"]
            fills.append(f)
        # cash: buys spend settled cash; sale proceeds (notional + pnl) settle T+1
        for f in fills:
            if f["status"] == "filled":
                st["settled_cash"] -= f["notional"]
                st["unsettled"].append({"amount": f["notional"] + f["pnl"], "settles": next_bday(date)})
        # open option positions: exit at 15:55 on expiry day or when worth >= target x entry; else mark at the close
        keep, pos_value = [], 0.0
        for ps in st["positions"]:
            if ps["symbol"] not in bars_cache:
                bars_cache[ps["symbol"]] = intraday(ps["symbol"], date)
            bars = bars_cache[ps["symbol"]]
            if bars is None or bars.empty:
                keep.append(ps); pos_value += ps.get("last_mark", ps["entry_price"]) * ps["contracts"] * 100; continue
            b = bars[bars.index <= close_out]
            t1, S1 = b.index[-1], float(b.Close.iloc[-1])
            mid = opt_value(ps["symbol"], ps["kind"], ps["strike"], ps["expiry"], S1, t1, date, octx)
            bid = max(mid - opt_half_spread(sim, mid, t1), 0.0)
            target = ag.cfg.get("take_profit_mult", 2.0) * ps["entry_price"]
            reason = "expiry" if date >= ps["expiry"] else ("target" if bid >= target else None)
            if reason:
                gross = bid * ps["contracts"] * 100
                comm = rules["opt_commission"] * ps["contracts"] if bid > 0 else 0.0
                proceeds = max(gross - comm, 0.0)
                st["unsettled"].append({"amount": proceeds, "settles": next_bday(date)})
                fills.append({"symbol": ps["symbol"], "status": "option sold", "call_id": ps["call_id"],
                              "contract": f"{ps['strike']:g}{ps['kind']} {ps['expiry']}", "exit_time": str(t1),
                              "stock": round(S1, 2), "exit": round(bid, 3), "reason": reason, "notional": ps["cost"],
                              "pnl": round(proceeds - ps["cost"], 4), "ret": proceeds / ps["cost"] - 1})
            else:
                ps["last_mark"] = bid
                keep.append(ps)
                pos_value += bid * ps["contracts"] * 100
        st["positions"] = keep
        end_equity = st["settled_cash"] + sum(u["amount"] for u in st["unsettled"]) + pos_value + spread_value
        st["last_equity"] = end_equity
        st["days"] = st.get("days", 0) + 1
        st["peak"] = max(st.get("peak", st["start_cash"]), end_equity)
        ag.save(st)
        pd.DataFrame(fills).to_csv(ff, index=False)
        eq = ag.path("equity.csv")
        row = pd.DataFrame([{"date": date, "equity": round(end_equity, 4), "day_pnl": round(end_equity - start_equity, 4),
                             "drawdown": round(end_equity / st["peak"] - 1, 6)}])
        row.to_csv(eq, mode="a", header=not eq.exists(), index=False)
        lines = [f"# {ag.name}: {date}", "", f"Equity {start_equity:.2f} -> **{end_equity:.2f}** "
                 f"({end_equity - start_equity:+.2f}, {end_equity / start_equity - 1:+.2%}); drawdown from peak "
                 f"{end_equity / st['peak'] - 1:.2%}",
                 (f"Decided at {ag.cfg['decide_at']} ET on bars before then (replayed); open spreads checked minute by "
                  "minute. Option prices are MODELED (Black-Scholes, options.py), not real quotes." if spreads else
                  f"Decided live at the checkpoints {', '.join(ag.cfg['checkpoints'])} ET on bars before each decision; "
                  "fills simulated on the day's 1-minute bars." if cpoint else
                  ((f"Opening orders placed at {placed} ET; then d" if teamed and placed is not None else "D")
                   + f"ecided minute by minute {ag.cfg['decide_at']}-{ag.cfg['last_entry']} ET "
                   + ("with the team's shared notes " if teamed else "") + "(replayed on bars before each minute)."
                   if scanning else f"Orders placed at {placed} ET; active from {active_from}.")), ""]
        def _line(f):
            if f["status"] == "filled":
                return (f"- {f['symbol']}: " + (f"ordered {f['placed_at'][11:16]}, " if f.get("placed_at") else "") + f"filled {f['qty']:.4f} sh @ {f['entry']:.2f} ({f['entry_time'][11:16]}) -> "
                        f"{f['exit']:.2f} ({f['exit_time'][11:16]}, {f['reason']}), P&L {f['pnl']:+.2f} ({f['ret']:+.2%}), fees {f['fees']:.3f}")
            if f["status"] == "option bought":
                return (f"- {f['call_id']} {f['symbol']} {f['contract']}: bought {f['contracts']:.4f} contracts @ {f['entry']:.2f} "
                        f"(model mid {f['model_mid']:.2f}, stock {f['stock']}, {f['entry_time'][11:16]}) for ${f['notional']:.2f}"
                        + (f" — FRACTIONAL: {f['real_account_note']}" if f.get("real_account_note") else "") + " [MODELED price]")
            if f["status"] == "option sold":
                return (f"- {f['call_id']} {f['symbol']} {f['contract']}: sold @ {f['exit']:.2f} ({f['reason']}, stock {f['stock']}), "
                        f"P&L {f['pnl']:+.2f} ({f['ret']:+.0%}) [MODELED price]")
            if f["status"] == "spread bought":
                return (f"- {f['symbol']} {f['contract']}: bought {f['contracts']:.4f} spreads @ {f['entry']:.2f} debit "
                        f"(model mid {f['model_mid']:.2f}, stock {f['stock']}, {f['entry_time'][11:16]}) for ${f['notional']:.2f}; "
                        f"exit by {f['exit_by']} — FRACTIONAL: {f['real_account_note']} [MODELED price]")
            if f["status"] == "spread sold":
                return (f"- {f['symbol']} {f['contract']}: sold @ {f['exit']:.2f} ({f['reason']} {f['exit_time'][5:16]}, stock {f['stock']}), "
                        f"P&L {f['pnl']:+.2f} ({f['ret']:+.0%}) [MODELED price]")
            return (f"- {f['symbol']}: " + (f"ordered {f['placed_at'][11:16]}, " if f.get("placed_at") else "")
                    + f"{f['status']} ({f.get('why', '')})")
        lines += [_line(f) for f in fills] or ["- no orders"]
        for ps in st["positions"]:
            lines.append(f"- holding {ps['call_id']} {ps['symbol']} {ps['strike']:g}{ps['kind']} {ps['expiry']}: "
                         f"{ps['contracts']:.4f} contracts, entry {ps['entry_price']:.2f}, marked {ps.get('last_mark', 0):.2f} (bid, MODELED)")
        for sp in st.get("spreads", []):
            lines.append(f"- holding {sp['symbol']} {sp['label']}: {sp['contracts']:.4f} spreads, entry {sp['entry_debit']:.2f}, "
                         f"marked {sp.get('last_mark', 0):.2f} (bid, MODELED), exit by {sp['exit_by']}")
        if ag.cfg.get("log_earnings_reaction"):  # shadow only: what the E002 skip would have touched
            react = reaction_day_symbols(root, date)
            hit = [f for f in fills if f["status"] == "filled" and react and f["symbol"] in react]
            lines.append("- E002 shadow (no effect on trades): " + (
                "earnings calendar missing" if react is None else
                ", ".join(f"{f['symbol']} was on its earnings reaction day (bought {f['entry_time'][11:16]}, "
                          f"{f['ret']:+.2%})" for f in hit) or f"no trade in a reaction-day stock (today: {', '.join(react) or 'none'})"))
        lines += ["", "Decision notes:"] + [f"- {n}" for n in rec.get("notes", [])]
        ag.path("journal", f"{date}.md").write_text("\n".join(lines) + "\n")
        print("\n".join(lines[:4]))


def status(root, name):
    ag = Agent(root, name)
    st = ag.state()
    eq = pd.read_csv(ag.dir / "equity.csv") if (ag.dir / "equity.csv").exists() else pd.DataFrame()
    total = st.get("last_equity", st["settled_cash"] + sum(u["amount"] for u in st["unsettled"]))
    print(f"{name}: equity {total:.2f} from {st['start_cash']:.2f} ({total / st['start_cash'] - 1:+.2%}) over {st.get('days', 0)} days")
    if len(eq):
        print(f"  worst day {eq.day_pnl.min():+.2f}, max drawdown {eq.drawdown.min():.2%}")


def compare(root):
    root = Path(root)
    rules = {**DEFAULT_RULES, **json.loads((root / "market_rules.json").read_text())}
    agents = sorted(p.name for p in (root / "agents").iterdir() if (p / "state.json").exists())
    days = {a: Agent(root, a).state().get("days", 0) for a in agents}
    need = rules["unlock_after_days"]
    ready = [a for a in agents if days[a] >= need]
    if not ready:
        print(f"LOCKED: no agent has {need} trading days yet "
              f"(now: {', '.join(f'{a} {d}' for a, d in days.items())})."); return
    lines = ["# Agent comparison", "", f"Each agent appears once it has {need} trading days. Agents that started on "
             "different days are not on identical days; compare those only over their common days.", "",
             "| Agent | Since | Days | Equity | Return | Worst day | Max drawdown | Trades | Win rate | Avg trade |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for a in ready:
        ag = Agent(root, a); st = ag.state()
        eq = pd.read_csv(ag.dir / "equity.csv")
        fills = pd.concat([pd.read_csv(p) for p in sorted((ag.dir / "fills").glob("*.csv")) if p.stat().st_size > 1] or [pd.DataFrame()])
        tr = fills[fills.get("status", pd.Series(dtype=str)).isin(["filled", "option sold", "spread sold"])] if len(fills) else fills
        total = eq.equity.iloc[-1]
        lines.append(f"| {a} | {eq.date.iloc[0]} | {len(eq)} | {total:.2f} | {total / st['start_cash'] - 1:+.2%} | {eq.day_pnl.min():+.2f} | "
                     f"{eq.drawdown.min():.2%} | {len(tr)} | {(tr.pnl > 0).mean() if len(tr) else 0:.0%} | "
                     f"{tr.ret.mean() if len(tr) else 0:+.2%} |")
    waiting = [a for a in agents if days[a] < need]
    if waiting:
        lines += ["", "Not shown yet (fewer than %d trading days): %s." % (need, ", ".join(f"{a} ({days[a]})" for a in waiting))]
    (root / "COMPARISON.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def init(root, start):
    root = Path(root)
    (root / "agents").mkdir(parents=True, exist_ok=True)
    for name in sorted(p.name for p in (root / "agents").iterdir() if p.is_dir()):
        d = root / "agents" / name
        if (d / "state.json").exists():
            print(f"{name}: exists, untouched"); continue
        if not (d / "config.json").exists():
            continue  # only agents with pre-registered rules get an account
        d.mkdir(parents=True, exist_ok=True)
        (d / "state.json").write_text(json.dumps({"start": start, "start_cash": 1000.0, "settled_cash": 1000.0,
                                                  "unsettled": [], "days": 0, "peak": 1000.0}, indent=1))
        print(f"{name}: created with $1000")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "decide", "checkpoint", "execute", "status", "compare"])
    ap.add_argument("--root", required=True)
    ap.add_argument("--agent")
    ap.add_argument("--date", default=pd.Timestamp.now(tz=ET).strftime("%Y-%m-%d"))
    ap.add_argument("--forecast-dir", default="lab/forecast")
    ap.add_argument("--start", default=None)
    ap.add_argument("--as-of", default=None, help="TEST ONLY: pretend the decision happens at HH:MM ET on --date")
    a = ap.parse_args()
    if a.cmd == "init":
        init(a.root, a.start or a.date)
    elif a.cmd == "decide":
        decide(a.root, a.agent, a.date, a.forecast_dir, a.as_of)
    elif a.cmd == "checkpoint":
        checkpoint(a.root, a.date, a.forecast_dir, a.as_of)
    elif a.cmd == "execute":
        execute(a.root, a.date, a.forecast_dir)
    elif a.cmd == "status":
        status(a.root, a.agent)
    else:
        compare(a.root)


if __name__ == "__main__":
    main()
