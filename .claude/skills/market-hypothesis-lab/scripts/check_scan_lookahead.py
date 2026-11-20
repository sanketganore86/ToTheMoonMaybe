# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy", "yfinance>=0.2.40", "requests"]
# ///
"""Lookahead check for the minute-by-minute replays: careful v2 (paper.scan_day) and, with --team, the
bold2 + careful3 team with shared notes (paper.team_day).

For each date, replays the day with the real rules and with two loosened rule sets that force many
orders and cancellations, then cuts every symbol's bars at many decision times T and replays again.
Every order placed at or before T must be identical in both runs; any difference means a decision
used data from after its own minute. Intraday bars come through paper.intraday (polite, cached).

  uv run check_scan_lookahead.py --lab lab 2026-10-19 2026-10-20
  uv run check_scan_lookahead.py --lab lab --team 2026-10-20 2026-10-21
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
import paper
ap = argparse.ArgumentParser(); ap.add_argument("--lab", default="lab"); ap.add_argument("--team", action="store_true")
ap.add_argument("dates", nargs="+")
args = ap.parse_args()
lab = Path(args.lab)
rules = {**paper.DEFAULT_RULES, **json.loads((lab / "paper/market_rules.json").read_text())}
base = json.loads((lab / "paper/agents/careful/config.json").read_text())
loose = {**base, "min_room_pct": -1, "min_p_touch_up1": 0, "limit_ttl_min": 3}   # forces many orders
fails = checks = 0


def team_check(date):
    """Replay the team with its real rules and with loosened ones (many orders, cancellations, stops and shared
    notes), cut the bars at every decision time and more, and require identical orders up to each cut."""
    global fails, checks
    fc = paper.champion_forecast(lab / "forecast", date)
    full = {s: paper.intraday(s, date) for s in fc.index}
    close_out = pd.Timestamp(f"{date} 15:55")
    cfgs = {n: json.loads((lab / f"paper/agents/{n}/config.json").read_text()) for n in ("bold2", "careful3")}
    looser = {"bold2": {"limit_ttl_min": 3, "target_pct": 0.004, "stop_pct": 0.004},
              "careful3": {"min_room_pct": -1, "min_p_touch_up1": 0, "limit_ttl_min": 3}}
    expiring = {n: {**v, "entry_limit_offset": -0.004} for n, v in looser.items()}   # most limits cancelled
    for name, adj in [("rules", {}), ("loose", looser), ("expiring", expiring)]:
        def run(bars):
            members = []
            for n, c in cfgs.items():
                ag = Ag(); ag.name, ag.cfg = n, {**c, **adj.get(n, {})}
                op = None
                if c["decision"] == "open_then_scan":
                    op = {"placed_at": f"{date}T08:15:00-04:00", "orders": paper.opening_orders(ag.cfg, fc, 1000.0), "notes": []}
                members.append({"ag": ag, "equity": 1000.0, "settled_cash": 1000.0, "opening": op})
            return paper.team_day(members, rules, fc, dict(bars), date, close_out)
        out, posted = run(full)
        orders = {n: [o for o in rec["orders"] if "placed_at" in o] for n, (rec, _) in out.items()}
        cuts = sorted({pd.Timestamp(o["placed_at"]) for v in orders.values() for o in v}
                      | {k for k, *_ in posted} | set(pd.date_range(f"{date} 09:45", f"{date} 15:30", freq="29min")))
        for T in cuts:
            out2, _ = run({s: b[b.index < T] for s, b in full.items()})
            for n in orders:
                a = [o for o in orders[n] if pd.Timestamp(o["placed_at"]) <= T]
                b = [o for o in out2[n][0]["orders"] if "placed_at" in o and pd.Timestamp(o["placed_at"]) <= T]
                checks += 1
                if a != b:
                    fails += 1; print("MISMATCH", date, name, n, T, a[-1:], b[-1:])
        skips = sum("shared note" in x for rec, _ in out.values() for x in rec["notes"])
        print(f"{date} team {name}: " + ", ".join(f"{n} {len(v)} orders/{sum(f['status'] == 'filled' for f in out[n][1])} filled"
                                                for n, v in orders.items())
              + f"; {len(posted)} notes posted, {skips} skips from notes; cuts checked: {len(cuts)}")


class Ag: pass


for date in (args.dates if args.team else []):
    team_check(date)
for date in ([] if args.team else args.dates):
    fc = paper.champion_forecast(lab / "forecast", date)
    full = {s: paper.intraday(s, date) for s in fc.index}
    close_out = pd.Timestamp(f"{date} 15:55")
    for name, cfg in [("rules", base), ("loose", loose), ("expiring", {**loose, "entry_limit_offset": -0.004})]:
        ag = Ag(); ag.name, ag.cfg = "careful", cfg
        rec, fills = paper.scan_day(ag, rules, fc, dict(full), 1000.0, 1000.0, date, close_out)
        n = len(rec["orders"])
        cuts = sorted({pd.Timestamp(o["placed_at"]) for o in rec["orders"]} | set(pd.date_range(f"{date} 10:15", f"{date} 15:00", freq="37min")))
        for T in cuts:
            trunc = {s: b[b.index < T] for s, b in full.items()}
            r2, _ = paper.scan_day(ag, rules, fc, trunc, 1000.0, 1000.0, date, close_out)
            a = [o for o in rec["orders"] if pd.Timestamp(o["placed_at"]) <= T]
            b = [o for o in r2["orders"] if pd.Timestamp(o["placed_at"]) <= T]
            checks += 1
            if a != b:
                fails += 1; print("MISMATCH", date, name, T, a[-1:], b[-1:])
        filled = sum(f["status"] == "filled" for f in fills)
        print(f"{date} {name}: {n} orders, {filled} filled; truncation cuts checked: {len(cuts)}")
print(f"lookahead checks: {checks}, mismatches: {fails}")
sys.exit(1 if fails else 0)
