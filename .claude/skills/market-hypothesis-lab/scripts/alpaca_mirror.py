# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Mirror paper agents' OPENING orders to Alpaca PAPER accounts, to test real broker plumbing.

PAPER ONLY. The base URL is fixed to Alpaca's paper endpoint, and every step also refuses an account
whose number does not start with "PA" (Alpaca's paper accounts). There is no live-trading switch.

What is mirrored: pre-open agents' market buys at the open (season 1: bold, bold2's opening buys; season 2:
bold v3), and checkpoint agents' live decisions (season 2: careful v3, hybrid) as bracket limit orders at each
checkpoint. Sizes are the agent's simulated notional x `scale`, rounded DOWN to whole shares, so the broker can
hold the exits.

Steps (ET), one dedicated Alpaca paper account per agent (keys from env <ENV>_KEY_ID / <ENV>_SECRET_KEY):
  place   before 09:28  market buys queued for the open (time_in_force "day"); also sells, on the open,
                        anything left over from a failed close the day before. Not "opg": Alpaca's paper
                        accounts expired every market-on-open order on 2026-11-06 (a known paper issue)
  exits   09:30-09:45   reads the opening fills, then places one OCO per position at fill x (1 +/- pct):
                        a take-profit limit and a stop, held by Alpaca (day orders). A buy that was cancelled
                        or expired with nothing filled is sent once more as a market order, until 09:40
  checkpoint 10:15/11:00/12:00/13:00/14:00, right after `paper.py checkpoint`: settles earlier checkpoint
                        orders (cancels unfilled ones at their cancel time) and sends the new decisions as
                        bracket orders (limit buy + take-profit + stop at the agent's own prices)
  close   15:55         cancels open orders, waits until they are gone, sells every position at market and
                        checks that it is flat (one retry). On 2026-11-06 a one-call "close all" answered
                        HTTP 207 yet left the SPY test shares held, probably because the exit pair still
                        reserved them; the next morning's step sells anything left over on the open
  record  after 16:30   saves the day's broker fills and compares them with the simulated fills
  check   any time      read-only: connects to each account, prints paper/status/equity; places nothing
  test    09:35-15:30   plumbing test, run by hand: buys `test_qty` (default 1) share of `test_symbol` (default
                        SPY) at market in each account, places its +/-1% exit pair, and leaves it for the 15:55
                        close. Kept apart from the agents' comparison (it is not an agent's trade)

Usage (root = lab/paper; broker config in <root>/broker/config.json):
  uv run alpaca_mirror.py place  --root lab/paper [--date D]
  uv run alpaca_mirror.py exits  --root lab/paper [--date D]
  uv run alpaca_mirror.py checkpoint --root lab/paper2 [--date D]
  uv run alpaca_mirror.py close  --root lab/paper [--date D]
  uv run alpaca_mirror.py record --root lab/paper [--date D]
  uv run alpaca_mirror.py check  --root lab/paper
  uv run alpaca_mirror.py test   --root lab/paper [--date D]
  add --now HH:MM to pretend the time (TEST ONLY; never in the workflow)

An agent without keys is skipped with a message, so the steps are harmless before the secrets exist.
Every request goes through polite.py (Alpaca allows 200/min; we use at most 2/s).
"""
import argparse
import csv
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
import polite  # noqa: E402

PAPER_URL = "https://paper-api.alpaca.markets"
HOST = "paper-api.alpaca.markets"
ET = ZoneInfo("America/New_York")
TAG = "mhl"  # prefix of our client_order_ids


class BrokerError(RuntimeError):
    pass


class Clock:
    """Wall clock in ET. --now (tests only) shifts it to that time on --date, and makes sleeps instant."""

    def __init__(self, date, now=None):
        self.offset = timedelta(0)
        if now:
            fake = datetime.fromisoformat(f"{date}T{now}").replace(tzinfo=ET)
            self.offset = fake - datetime.now(ET)
        self.fake = bool(now)

    def now(self):
        return datetime.now(ET) + self.offset

    def sleep_until(self, hhmmss, date):
        target = datetime.fromisoformat(f"{date}T{hhmmss}").replace(tzinfo=ET)
        wait = (target - self.now()).total_seconds()
        if wait > 0:
            print(f"  waiting {wait:.0f}s until {hhmmss} ET", flush=True)
            if self.fake:
                self.offset += timedelta(seconds=wait)
            else:
                time.sleep(wait)

    def sleep(self, s):
        if self.fake:
            self.offset += timedelta(seconds=s)
        else:
            time.sleep(s)


class Paper:
    """Minimal Alpaca paper Trading API client. Never prints or stores the keys."""

    def __init__(self, key, secret):
        self.headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

    def _send(self, method, path, params=None, body=None):
        import requests
        for attempt in range(4):
            polite.wait(HOST)
            try:
                r = requests.request(method, PAPER_URL + path, params=params, json=body,
                                     headers=self.headers, timeout=30)
            except requests.RequestException as e:
                polite.report_failure(HOST, 15 * 2 ** attempt)
                print(f"  [alpaca] {method} {path}: {type(e).__name__}; retrying", flush=True)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                ra = r.headers.get("Retry-After", "")
                polite.report_failure(HOST, int(ra) if ra.isdigit() else 15 * 2 ** attempt)
                print(f"  [alpaca] {method} {path}: HTTP {r.status_code}; retrying", flush=True)
                continue
            polite.report_success(HOST)
            try:
                data = r.json() if r.content else None
            except ValueError:
                data = {"text": r.text[:300]}
            return r.status_code, data
        raise BrokerError(f"{method} {path}: gave up after 4 attempts")

    def get(self, path, **params):
        st, data = self._send("GET", path, params=params or None)
        if st != 200:
            raise BrokerError(f"GET {path}: HTTP {st} {data}")
        return data

    def post(self, path, body):
        return self._send("POST", path, body=body)

    def delete(self, path, **params):
        return self._send("DELETE", path, params=params or None)


# ------------------------------------------------------------------ setup
def load_cfg(root):
    return json.loads((Path(root) / "broker" / "config.json").read_text())


def connect(name, acfg):
    """The agent's paper client, or None (with the reason printed) when it must not trade."""
    env = acfg["env"]
    key, secret = os.environ.get(f"{env}_KEY_ID"), os.environ.get(f"{env}_SECRET_KEY")
    if not key or not secret:
        print(f"{name}: skipped (no {env}_KEY_ID / {env}_SECRET_KEY secrets)")
        return None, None
    cl = Paper(key, secret)
    acct = cl.get("/v2/account")
    if not str(acct.get("account_number", "")).startswith("PA"):
        raise BrokerError(f"{name}: account is not an Alpaca PAPER account; refusing to trade")
    if acct.get("status") != "ACTIVE" or acct.get("trading_blocked") or acct.get("account_blocked"):
        print(f"{name}: skipped (account status {acct.get('status')}, trading blocked {acct.get('trading_blocked')})")
        return None, None
    return cl, acct


def rec_path(root, name, date):
    return Path(root) / "broker" / name / f"{date}.json"


def load_rec(root, name, date):
    p = rec_path(root, name, date)
    return json.loads(p.read_text()) if p.exists() else {"agent": name, "date": date, "log": []}


def save_rec(root, name, date, rec):
    p = rec_path(root, name, date)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=1) + "\n")


def log(rec, clock, msg):
    line = f"{clock.now():%H:%M:%S} {msg}"
    rec["log"].append(line)
    print(f"  {line}", flush=True)


def coid(name, date, sym, kind):
    return f"{TAG}-{name}-{date}-{sym}-{kind}"


def agent_decision(root, name):
    p = Path(root) / "agents" / name / "config.json"
    return json.loads(p.read_text()).get("decision", "") if p.exists() else ""


def agent_orders(root, name, date):
    p = Path(root) / "agents" / name / "orders" / f"{date}.json"
    if not p.exists():
        return None
    rec = json.loads(p.read_text())
    rec = rec.get("opening", rec) if "decision" in rec else rec  # after the evening run the morning record is nested
    return [o for o in (rec or {}).get("orders", []) if o.get("side") == "buy" and o.get("type") == "market"]


def prev_closes(forecast_dir, date):
    p = Path(forecast_dir) / "predictions" / f"{date}.csv"
    if not p.exists():
        print(f"no forecasts for {date} ({p}); no buys can be sized")
        return {}
    with open(p) as fh:
        return {r["symbol"]: float(r["prev_close"]) for r in csv.DictReader(fh) if r.get("role", "champion") == "champion"}


def active(cfg, date):
    if not cfg.get("enabled", False):
        print("broker mirror disabled in config.json"); return False
    if date < cfg["start"]:
        print(f"broker mirror starts {cfg['start']}; nothing to do on {date}"); return False
    if datetime.fromisoformat(date).weekday() > 4:
        print("weekend; nothing to do"); return False
    return True


# ------------------------------------------------------------------ steps
def place(root, date, forecast_dir, clock):
    cfg = load_cfg(root)
    if not active(cfg, date):
        return
    t = clock.now().strftime("%H:%M")
    if not ("04:00" <= t <= "09:27"):
        print(f"{t} ET is outside 04:00-09:27: too late for market-on-open orders; nothing placed"); return
    closes = prev_closes(forecast_dir, date)
    for name, acfg in cfg["agents"].items():
        cl, acct = connect(name, acfg)
        if cl is None:
            continue
        rec = load_rec(root, name, date)
        rec["equity_before"] = float(acct["equity"])
        if float(acct["equity"]) < cfg["min_equity"]:
            log(rec, clock, f"equity {acct['equity']} is under {cfg['min_equity']} (pattern-day-trader limit); nothing placed")
            save_rec(root, name, date, rec); continue
        for p in cl.get("/v2/positions"):  # a failed close yesterday: sell on the open
            st, d = cl.post("/v2/orders", {"symbol": p["symbol"], "qty": p["qty"], "side": "sell", "type": "market",
                                           "time_in_force": "day", "client_order_id": coid(name, date, p["symbol"], "leftover")})
            dup = st == 422 and "unique" in json.dumps(d).lower()
            log(rec, clock, f"LEFTOVER {p['qty']} {p['symbol']} from an earlier day: sell on the open -> "
                            f"{'already placed' if dup else 'OK' if st == 200 else f'REJECTED HTTP {st}: {d}'}")
        if agent_decision(root, name) not in ("pre_open", "open_then_scan"):  # it buys at its checkpoints instead
            save_rec(root, name, date, rec); continue
        orders = agent_orders(root, name, date)
        if orders is None:
            log(rec, clock, "no agent orders file yet; nothing placed")
        rec.setdefault("entries", {})
        for o in orders or []:
            sym = o["symbol"]
            if sym not in closes:
                log(rec, clock, f"{sym}: no previous close to size the order; skipped"); continue
            amt = min(o["notional"] * cfg["scale"], cfg["max_order_notional"])
            qty = math.floor(amt / closes[sym])
            if qty < 1:
                log(rec, clock, f"{sym}: ${amt:.0f} buys less than one share at {closes[sym]:.2f}; skipped"); continue
            st, d = cl.post("/v2/orders", {"symbol": sym, "qty": str(qty), "side": "buy", "type": "market",
                                           "time_in_force": "day", "client_order_id": coid(name, date, sym, "entry")})
            dup = st == 422 and "unique" in json.dumps(d).lower()
            ok = st == 200 or dup
            rec["entries"][sym] = {"qty": qty, "notional_target": round(amt, 2), "prev_close": closes[sym],
                                   "target_pct": o["target_pct"], "stop_pct": o["stop_pct"], "placed": ok,
                                   "coid": coid(name, date, sym, "entry")}
            log(rec, clock, f"BUY {qty} {sym} market, queued for the open (~${qty * closes[sym]:.0f}) -> "
                            f"{'already placed' if dup else 'OK' if ok else f'REJECTED HTTP {st}: {d}'}")
        save_rec(root, name, date, rec)


def exits(root, date, clock):
    cfg = load_cfg(root)
    if not active(cfg, date):
        return
    if clock.now().strftime("%H:%M") < "09:15" or clock.now().strftime("%H:%M") > "10:00":
        print("exits run only between 09:15 and 10:00 ET; nothing done"); return
    clock.sleep_until("09:30:20", date)
    for name, acfg in cfg["agents"].items():
        cl, _ = connect(name, acfg)
        if cl is None:
            continue
        rec = load_rec(root, name, date)
        pending = {s: e for s, e in rec.get("entries", {}).items() if e.get("placed") and "fill" not in e}
        deadline = datetime.fromisoformat(f"{date}T09:45:00").replace(tzinfo=ET)
        while pending and clock.now() < deadline:
            for sym in list(pending):
                e = pending[sym]
                o = cl.get("/v2/orders:by_client_order_id", client_order_id=e.get("coid", coid(name, date, sym, "entry")))
                done = o["status"] in ("canceled", "expired", "rejected")
                if o["status"] == "filled" or (done and float(o.get("filled_qty") or 0) > 0):
                    # filled, or ended part-filled: protect whatever was bought
                    pending.pop(sym)
                    if o["status"] != "filled":
                        log(rec, clock, f"{sym}: buy {o['status']} after a partial fill of {o['filled_qty']}")
                    e.update(fill=float(o["filled_avg_price"]), filled_qty=o["filled_qty"], filled_at=o["filled_at"])
                    e.update(exit_order(cl, rec, clock, name, date, sym, e))
                elif done and not e.get("retried") and clock.now().strftime("%H:%M") < "09:40":
                    # nothing bought: send it once more as a plain market order (the agent's buy is "at the open")
                    e.update(entry_status=o["status"], retried=True, coid=coid(name, date, sym, "entry2"))
                    st, d = cl.post("/v2/orders", {"symbol": sym, "qty": str(e["qty"]), "side": "buy", "type": "market",
                                                   "time_in_force": "day", "client_order_id": e["coid"]})
                    dup = st == 422 and "unique" in json.dumps(d).lower()
                    log(rec, clock, f"{sym}: buy {o['status']} with nothing filled; sent again as a market order -> "
                                    f"{'already placed' if dup else 'OK' if st == 200 else f'REJECTED HTTP {st}: {d}'}")
                    if not (st == 200 or dup):
                        pending.pop(sym)
                elif done:
                    pending.pop(sym)["entry_status"] = o["status"]
                    log(rec, clock, f"{sym}: buy {o['status']}; no position")
            if pending:
                clock.sleep(15)
        for sym in pending:
            log(rec, clock, f"{sym}: no fill by 09:45; the 15:55 close will sell anything that fills later")
        save_rec(root, name, date, rec)


def exit_order(cl, rec, clock, name, date, sym, e, kind="exit"):
    tp = round(e["fill"] * (1 + e["target_pct"]), 2)
    sl = round(e["fill"] * (1 - e["stop_pct"]), 2)
    st, d = cl.post("/v2/orders", {"symbol": sym, "qty": e["filled_qty"], "side": "sell", "type": "limit",
                                   "time_in_force": "day", "order_class": "oco", "take_profit": {"limit_price": tp},
                                   "stop_loss": {"stop_price": sl}, "client_order_id": coid(name, date, sym, kind)})
    if st == 200:
        log(rec, clock, f"{sym}: filled {e['filled_qty']} @ {e['fill']:.2f}; exits placed: target {tp}, stop {sl}")
        return {"target": tp, "stop": sl, "exit_order": d["id"], "stop_leg": (d.get("legs") or [{}])[0].get("id")}
    # rejected (e.g. the price is already past the stop): protect capital, sell now
    st2, d2 = cl.post("/v2/orders", {"symbol": sym, "qty": e["filled_qty"], "side": "sell", "type": "market",
                                     "time_in_force": "day", "client_order_id": coid(name, date, sym, kind + "now")})
    log(rec, clock, f"{sym}: exit pair REJECTED (HTTP {st}: {d}); sold at market -> HTTP {st2}")
    return {"target": tp, "stop": sl, "exit_rejected": str(d)[:200]}


def checkpoint(root, date, clock):
    """Mirror the live checkpoint decisions (agents with decision "checkpoints", e.g. careful v3 and hybrid).
    Run right after `paper.py checkpoint` at each checkpoint time. First it settles earlier orders: a filled one
    is already protected by its bracket legs; one still unfilled at its cancel time is cancelled (a part-fill
    gets its own target/stop pair). Then it sends each new decision once, as a bracket order: a day limit buy at
    the agent's limit price with a take-profit at its target price and a stop at its stop price, the same prices
    the simulator uses. Sizes: the agent's notional x scale, rounded down to whole shares."""
    cfg = load_cfg(root)
    if not active(cfg, date):
        return
    t = clock.now().strftime("%H:%M")
    if not ("10:00" <= t <= "15:00"):
        print(f"{t} ET is outside 10:00-15:00: no checkpoint orders now"); return
    for name, acfg in cfg["agents"].items():
        if agent_decision(root, name) != "checkpoints":
            continue
        cl, acct = connect(name, acfg)
        if cl is None:
            continue
        rec = load_rec(root, name, date)
        rec.setdefault("equity_before", float(acct["equity"]))
        if float(acct["equity"]) < cfg["min_equity"]:
            log(rec, clock, f"equity {acct['equity']} is under {cfg['min_equity']}; nothing placed")
            save_rec(root, name, date, rec); continue
        sent = rec.setdefault("checkpoint_orders", {})
        for c, e in sent.items():  # 1) earlier orders: filled, done, or due to be cancelled
            if e.get("final"):
                continue
            o = cl.get("/v2/orders:by_client_order_id", client_order_id=c)
            if o["status"] == "filled":
                e.update(final=True, fill=float(o["filled_avg_price"]), filled_qty=o["filled_qty"], filled_at=o["filled_at"])
                log(rec, clock, f"{e['symbol']}: filled {o['filled_qty']} @ {float(o['filled_avg_price']):.2f}; "
                                f"its target {e['target']} and stop {e['stop']} are held by the broker")
                continue
            due = clock.now() >= datetime.fromisoformat(e["cancel_at"]).replace(tzinfo=ET)
            if o["status"] not in ("canceled", "expired", "rejected"):
                if not due:
                    continue
                cl.delete(f"/v2/orders/{o['id']}")
                for _ in range(6):
                    clock.sleep(2)
                    o = cl.get("/v2/orders:by_client_order_id", client_order_id=c)
                    if o["status"] in ("canceled", "expired", "rejected", "filled"):
                        break
                if o["status"] == "filled":  # filled while we cancelled: the bracket protects it
                    e.update(final=True, fill=float(o["filled_avg_price"]), filled_qty=o["filled_qty"], filled_at=o["filled_at"])
                    log(rec, clock, f"{e['symbol']}: filled {o['filled_qty']} @ {float(o['filled_avg_price']):.2f} "
                                    "just before its cancel time; bracket exits held"); continue
            got = float(o.get("filled_qty") or 0)
            e.update(final=True, entry_status=o["status"], filled_qty=o.get("filled_qty"))
            log(rec, clock, f"{e['symbol']}: limit buy {o['status']} at its cancel time, {got:g} filled")
            if got > 0:  # protect a part-fill with its own pair (rejected if the bracket legs already hold the shares)
                st, d = cl.post("/v2/orders", {"symbol": e["symbol"], "qty": f"{got:g}", "side": "sell", "type": "limit",
                                               "time_in_force": "day", "order_class": "oco",
                                               "take_profit": {"limit_price": str(e["target"])},
                                               "stop_loss": {"stop_price": str(e["stop"])},
                                               "client_order_id": c + "x"})
                log(rec, clock, f"{e['symbol']}: exit pair for the part-fill -> "
                                f"{'OK' if st == 200 else f'not placed (HTTP {st}; the bracket legs may already hold them): {d}'}")
        p = Path(root) / "agents" / name / "orders" / f"{date}.json"
        rounds = json.loads(p.read_text()).get("rounds", []) if p.exists() else []
        for r in rounds:  # 2) new decisions, each sent once
            for o in r["orders"]:
                c = coid(name, date, o["symbol"], "cp" + r["checkpoint"].replace(":", ""))
                if c in sent or clock.now() < datetime.fromisoformat(o["decision_minute"]).replace(tzinfo=ET):
                    continue  # already sent, or (replay tests only) decided after this moment
                e = {"symbol": o["symbol"], "limit": o["limit"], "target": o["target_price"], "stop": o["stop_price"],
                     "cancel_at": o["cancel_at"], "checkpoint": r["checkpoint"]}
                sent[c] = e
                if clock.now() >= datetime.fromisoformat(o["cancel_at"]).replace(tzinfo=ET):
                    e.update(final=True, skipped="its cancel time had passed")
                    log(rec, clock, f"{o['symbol']}: {r['checkpoint']} order not sent, its cancel time had passed"); continue
                amt = min(o["notional"] * cfg["scale"], cfg["max_order_notional"])
                qty = math.floor(amt / o["limit"])
                if qty < 1:
                    e.update(final=True, skipped="less than one share")
                    log(rec, clock, f"{o['symbol']}: ${amt:.0f} buys less than one share at {o['limit']}; skipped"); continue
                st, d = cl.post("/v2/orders", {"symbol": o["symbol"], "qty": str(qty), "side": "buy", "type": "limit",
                                               "limit_price": str(o["limit"]), "time_in_force": "day",
                                               "order_class": "bracket",
                                               "take_profit": {"limit_price": str(o["target_price"])},
                                               "stop_loss": {"stop_price": str(o["stop_price"])},
                                               "client_order_id": c})
                dup = st == 422 and "unique" in json.dumps(d).lower()
                ok = st == 200 or dup
                e.update(qty=qty, placed=ok, final=not ok)
                log(rec, clock, f"{r['checkpoint']} BUY {qty} {o['symbol']} limit {o['limit']} (target {o['target_price']}, "
                                f"stop {o['stop_price']}, cancel {o['cancel_at'][11:16]}) -> "
                                f"{'already placed' if dup else 'OK' if ok else f'REJECTED HTTP {st}: {d}'}")
        save_rec(root, name, date, rec)


def test(root, date, clock):
    """Hand-run plumbing test: one small market buy per account, its exit pair, then the 15:55 close."""
    cfg = load_cfg(root)
    if not active(cfg, date):
        return
    t = clock.now().strftime("%H:%M")
    if not ("09:35" <= t <= "15:30"):
        print(f"{t} ET is outside 09:35-15:30: no test trade now"); return
    sym, qty = cfg.get("test_symbol", "SPY"), int(cfg.get("test_qty", 1))
    for name, acfg in cfg["agents"].items():
        cl, acct = connect(name, acfg)
        if cl is None:
            continue
        rec = load_rec(root, name, date)
        if float(acct["equity"]) < cfg["min_equity"]:
            log(rec, clock, f"TEST: equity {acct['equity']} is under {cfg['min_equity']}; nothing placed")
            save_rec(root, name, date, rec); continue
        if any(p["symbol"] == sym for p in cl.get("/v2/positions")):
            log(rec, clock, f"TEST: already holds {sym}; nothing placed")
            save_rec(root, name, date, rec); continue
        st, d = cl.post("/v2/orders", {"symbol": sym, "qty": str(qty), "side": "buy", "type": "market",
                                       "time_in_force": "day", "client_order_id": coid(name, date, sym, "test")})
        if st != 200:
            dup = st == 422 and "unique" in json.dumps(d).lower()
            log(rec, clock, f"TEST: BUY {qty} {sym} -> {'already placed today' if dup else f'REJECTED HTTP {st}: {d}'}")
            save_rec(root, name, date, rec); continue
        log(rec, clock, f"TEST: BUY {qty} {sym} market -> OK")
        e = {"qty": qty, "target_pct": 0.01, "stop_pct": 0.01}
        o = d
        for _ in range(12):  # up to ~60 s for the fill
            o = cl.get("/v2/orders:by_client_order_id", client_order_id=coid(name, date, sym, "test"))
            if o["status"] in ("filled", "canceled", "expired", "rejected"):
                break
            clock.sleep(5)
        if o["status"] != "filled":
            cl.delete(f"/v2/orders/{o['id']}")
            log(rec, clock, f"TEST: {sym} buy {o['status']} after 60 s (filled {o.get('filled_qty')}); cancelled the rest, "
                            "the 15:55 close sells any shares bought")
        else:
            e.update(fill=float(o["filled_avg_price"]), filled_qty=o["filled_qty"], filled_at=o["filled_at"])
            e.update(exit_order(cl, rec, clock, name, date, sym, e, kind="testexit"))
        rec.setdefault("test", {})[sym] = e
        save_rec(root, name, date, rec)


def close(root, date, clock):
    cfg = load_cfg(root)
    if not active(cfg, date):
        return
    t = clock.now().strftime("%H:%M")
    if not ("15:45" <= t <= "16:00"):
        print(f"{t} ET is outside 15:45-16:00: refusing to close positions now"); return
    clock.sleep_until("15:55:00", date)
    for name, acfg in cfg["agents"].items():
        cl, _ = connect(name, acfg)
        if cl is None:
            continue
        rec = load_rec(root, name, date)
        held = cl.get("/v2/positions")
        if not held:
            log(rec, clock, "15:55: no open positions")
            save_rec(root, name, date, rec); continue
        flat_close(cl, rec, clock, name, date, held)
        save_rec(root, name, date, rec)


def flat_close(cl, rec, clock, name, date, held):
    """Cancel every open order, wait until none is left (they reserve the shares), sell at market, verify flat."""
    st, _ = cl.delete("/v2/orders")
    for _ in range(10):  # up to ~30 s for the cancels to finish
        left = cl.get("/v2/orders", status="open")
        if not left:
            break
        clock.sleep(3)
    log(rec, clock, f"15:55: cancelled open orders (HTTP {st}); still open after the wait: {len(left)}")
    for attempt in (1, 2):
        sent = 0
        for p in held:
            qty = abs(float(p["qty"]))
            side = "sell" if float(p["qty"]) > 0 else "buy"
            st, d = cl.post("/v2/orders", {"symbol": p["symbol"], "qty": f"{qty:g}", "side": side, "type": "market",
                                           "time_in_force": "day",
                                           "client_order_id": coid(name, date, p["symbol"], f"close{attempt}")})
            log(rec, clock, f"15:55: {side.upper()} {qty:g} {p['symbol']} market (attempt {attempt}) -> "
                            f"{'OK' if st == 200 else f'REJECTED HTTP {st}: {d}'}")
            sent += st == 200
        for _ in range(12 if sent else 1):  # up to ~60 s for the fills (no wait when every sell was rejected)
            clock.sleep(5)
            held = cl.get("/v2/positions")
            if not held:
                log(rec, clock, "15:55: flat (no positions left)")
                return
        if attempt == 1:
            cl.delete("/v2/orders")  # whatever is stuck, before the second try
            clock.sleep(3)
    log(rec, clock, "WARNING: still holding " + ", ".join(f"{p['qty']} {p['symbol']}" for p in held)
                    + " after two tries; the next morning's step sells it on the open")


def opening_prices(forecast_dir, date):
    """The day's official opening prices, from the evening forecast score (scorecard.csv), if it has run."""
    p = Path(forecast_dir) / "scorecard.csv"
    if not p.exists():
        return {}
    with open(p) as fh:
        return {r["symbol"]: float(r["open"]) for r in csv.DictReader(fh)
                if r["date"] == date and r.get("role", "champion") == "champion" and r.get("open")}


def record(root, date, clock, forecast_dir="lab/forecast"):
    cfg = load_cfg(root)
    if not active(cfg, date):
        return
    rows = []
    opens = opening_prices(forecast_dir, date)
    for name, acfg in cfg["agents"].items():
        at_open = agent_decision(root, name) in ("pre_open", "open_then_scan")
        cl, acct = connect(name, acfg)
        if cl is None:
            continue
        rec = load_rec(root, name, date)
        fills = cl.get("/v2/account/activities/FILL", date=date, direction="asc", page_size=100)
        day = datetime.fromisoformat(date).replace(tzinfo=ET)
        orders = cl.get("/v2/orders", status="all", nested="true", limit=500,
                        after=day.isoformat(), until=(day + timedelta(days=1)).isoformat())
        kind = {}  # order id -> why it sold
        for o in orders:
            c = o.get("client_order_id", "")
            cp = c.rsplit("-", 1)[-1]
            kind[o["id"]] = "target" if c.endswith(("-exit", "-testexit")) or (cp.startswith("cp") and cp.endswith("x")) \
                else "time exit 15:55" if "-close" in c else \
                "market exit" if c.endswith(("-exitnow", "-testexitnow")) else "test buy" if c.endswith("-test") else \
                "leftover" if c.endswith("-leftover") else \
                "entry" if c.endswith(("-entry", "-entry2")) or (cp.startswith("cp") and cp[2:].isdigit()) else "time exit 15:55"
            for leg in o.get("legs") or []:  # OCO: the parent is the target, its leg the stop; bracket: both are legs
                kind[leg["id"]] = "target" if leg.get("type") == "limit" else "stop"
        by = {}
        for f in fills:
            b = by.setdefault(f["symbol"], {"buy": [], "sell": []})
            b[f["side"]].append((float(f["qty"]), float(f["price"]), f["transaction_time"], kind.get(f["order_id"], "?")))
        sim = sim_fills(root, name, date)
        rec["broker_fills"] = {}
        for sym, b in by.items():
            if not b["buy"] or not b["sell"]:
                continue
            if any(k == "test buy" for *_, k in b["buy"]):  # a hand-run plumbing test, not an agent's trade
                ent = sum(q * p for q, p, *_ in b["buy"]) / sum(q for q, *_ in b["buy"])
                ex = sum(q * p for q, p, *_ in b["sell"]) / sum(q for q, *_ in b["sell"])
                rec.setdefault("test_fills", {})[sym] = {"qty": sum(q for q, *_ in b["buy"]), "entry": round(ent, 4),
                                                         "exit": round(ex, 4), "exit_time": b["sell"][-1][2],
                                                         "reason": b["sell"][-1][3], "ret": round(ex / ent - 1, 6)}
                continue
            entry = sum(q * p for q, p, *_ in b["buy"]) / sum(q for q, *_ in b["buy"])
            exit_ = sum(q * p for q, p, *_ in b["sell"]) / sum(q for q, *_ in b["sell"])
            why = b["sell"][-1][3]
            ret = exit_ / entry - 1
            rec["broker_fills"][sym] = {"qty": sum(q for q, *_ in b["buy"]), "entry": round(entry, 4), "exit": round(exit_, 4),
                                        "exit_time": b["sell"][-1][2], "reason": why, "ret": round(ret, 6)}
            s = sim.get(sym, {})
            op = opens.get(sym) if at_open else None  # opening buys: how far each fill was from the real opening price
            rows.append({"date": date, "agent": name, "symbol": sym, "qty": rec["broker_fills"][sym]["qty"],
                         "broker_entry": round(entry, 4), "sim_entry": s.get("entry", ""),
                         "entry_diff_bps": round((entry / float(s["entry"]) - 1) * 1e4, 1) if s.get("entry") else "",
                         "broker_exit": round(exit_, 4), "sim_exit": s.get("exit", ""),
                         "broker_reason": why, "sim_reason": s.get("reason", ""),
                         "broker_ret": round(ret, 6), "sim_ret": round(float(s["ret"]), 6) if s.get("ret") else "",
                         "open_price": op or "",
                         "broker_vs_open_bps": round((entry / op - 1) * 1e4, 1) if op else "",
                         "sim_vs_open_bps": round((float(s["entry"]) / op - 1) * 1e4, 1) if op and s.get("entry") else ""})
        rec["equity_after"] = float(acct["equity"])
        held = cl.get("/v2/positions")
        rec["held_after_close"] = {p["symbol"]: p["qty"] for p in held}
        log(rec, clock, f"recorded {len(rec['broker_fills'])} round trips from {len(fills)} fills; account equity "
                        f"{acct['equity']}" + (f"; STILL HELD: {', '.join(f'{q} {s}' for s, q in rec['held_after_close'].items())}"
                                               " (sold on the next open)" if held else "; no positions held"))
        save_rec(root, name, date, rec)
    if rows:
        write_compare(root, date, rows)


def check(root):
    """Read-only: can each agent's keys reach its paper account, and may it trade? Places nothing."""
    cfg = load_cfg(root)
    print(f"broker mirror {'enabled' if cfg.get('enabled') else 'DISABLED'}, starts {cfg['start']}")
    for name, acfg in cfg["agents"].items():
        cl, acct = connect(name, acfg)
        if cl is None:
            continue
        held = cl.get("/v2/positions")
        eq, floor = float(acct["equity"]), cfg["min_equity"]
        low = "" if eq >= floor else f" (UNDER ${floor:,}: nothing would be placed)"
        print(f"{name}: paper account OK, status {acct['status']}, equity ${eq:,.2f}{low}, "
              f"pattern day trader flag {acct.get('pattern_day_trader')}, open positions {len(held)}")


def sim_fills(root, name, date):
    p = Path(root) / "agents" / name / "fills" / f"{date}.csv"
    if not p.exists() or p.stat().st_size < 5:
        return {}
    with open(p) as fh:
        return {r["symbol"]: r for r in csv.DictReader(fh) if r.get("status") == "filled"}


def write_compare(root, date, rows):
    p = Path(root) / "broker" / "compare.csv"
    old = []
    if p.exists():
        with open(p) as fh:
            old = [r for r in csv.DictReader(fh) if r["date"] != date]  # a re-run replaces that day
    allr = old + [{k: str(v) for k, v in r.items()} for r in rows]
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), restval="")
        w.writeheader(); w.writerows(allr)
    lines = ["# Broker mirror vs simulated fills (Alpaca PAPER)", "",
             "Alpaca's paper fills are simulated from live quotes, so this checks the order plumbing and our fill "
             "model's assumptions, not real-money execution. Returns are per share (sizes differ: whole shares at 10x).",
             "For buys at the open, \"vs open\" is how far the fill was from the day's official opening price: Alpaca's "
             "paper account fills queued market buys a few minutes late, so a large gap there flatters (or hurts) the "
             "broker column in a way a real account would not.", "",
             "| Agent | Round trips | Avg return broker | Avg return sim | Avg entry diff (bps) | Same exit reason "
             "| Broker vs open (bps) | Sim vs open (bps) |",
             "|---|---|---|---|---|---|---|---|"]
    for ag in sorted({r["agent"] for r in allr}):
        rr = [r for r in allr if r["agent"] == ag]
        both = [r for r in rr if r["sim_ret"] != ""]
        avg = lambda k, xs: sum(float(r[k]) for r in xs) / len(xs) if xs else float("nan")  # noqa: E731
        diffs = [r for r in rr if r["entry_diff_bps"] != ""]
        same = sum(r["broker_reason"] == r["sim_reason"] for r in both)
        bo = [r for r in rr if r.get("broker_vs_open_bps", "") != ""]
        so = [r for r in rr if r.get("sim_vs_open_bps", "") != ""]
        lines.append(f"| {ag} | {len(rr)} | {avg('broker_ret', rr):+.2%} | {avg('sim_ret', both):+.2%} | "
                     f"{avg('entry_diff_bps', diffs):+.1f} | {same}/{len(both)} | "
                     + (f"{avg('broker_vs_open_bps', bo):+.1f}" if bo else "n/a") + " | "
                     + (f"{avg('sim_vs_open_bps', so):+.1f}" if so else "n/a") + " |")
    lines += ["", "Per trade: `compare.csv`. Each day's orders, fills and log: `<agent>/<date>.json`."]
    (Path(root) / "broker" / "REPORT.md").write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["place", "exits", "checkpoint", "close", "record", "check", "test"])
    ap.add_argument("--root", required=True)
    ap.add_argument("--date", default=datetime.now(ET).strftime("%Y-%m-%d"))
    ap.add_argument("--forecast-dir", default="lab/forecast")
    ap.add_argument("--now", default=None, help="TEST ONLY: pretend it is HH:MM ET on --date")
    a = ap.parse_args()
    clock = Clock(a.date, a.now)
    {"place": lambda: place(a.root, a.date, a.forecast_dir, clock), "exits": lambda: exits(a.root, a.date, clock),
     "checkpoint": lambda: checkpoint(a.root, a.date, clock),
     "close": lambda: close(a.root, a.date, clock), "record": lambda: record(a.root, a.date, clock, a.forecast_dir),
     "check": lambda: check(a.root), "test": lambda: test(a.root, a.date, clock)}[a.cmd]()


if __name__ == "__main__":
    main()
