# /// script
# dependencies = ["requests", "pandas>=2", "yfinance>=0.2.40"]
# ///
"""Seeded random sample of the S&P 600 -> lab/smallcap/<T>/data with prices (2010+),
market series and insider data, all via the cache. Rerunnable: cached items are skipped."""
import sys
from pathlib import Path
sys.path.insert(0, ".claude/skills/market-hypothesis-lab/scripts")
import pandas as pd
import cache
from fetch_data import get_prices
import insider_bulk as ib

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=2026); ap.add_argument("--n", type=int, default=100)
ap.add_argument("--exclude-seed", type=int, default=None, help="drop the names drawn by this earlier seed")
ap.add_argument("--exclude-n", type=int, default=100); ap.add_argument("--out", default="lab/smallcap/universe.csv")
a = ap.parse_args()
SEED, N, START = a.seed, a.n, "2010-01-01"
pool = pd.read_csv("lab/smallcap/sp600_constituents.csv")
if a.exclude_seed is not None:  # disjoint universe: remove every name the earlier draw touched
    taken = set(pool.sample(n=a.exclude_n, random_state=a.exclude_seed).symbol)
    pool = pool[~pool.symbol.isin(taken)]
    print(f"excluded {len(taken)} names from seed {a.exclude_seed}; pool {len(pool)}", flush=True)
u = pool.sample(n=min(N, len(pool)), random_state=SEED)
keep = []
for sym, sector in u[["symbol", "sector"]].itertuples(index=False):
    try:
        get_prices(sym, quiet=True, start=START)
    except BaseException as e:  # delisted / renamed / throttled: skip, keep going
        print(f"{sym}: price fetch failed ({str(e)[:60]})", flush=True)
        continue
    p = cache.ROOT / f"prices/{cache.safe(sym)}.csv"
    first = pd.read_csv(p, index_col=0, parse_dates=True).index.min()
    if first > pd.Timestamp("2012-12-31"):
        print(f"{sym}: history starts {first.date()}, too short; skipped", flush=True)
        continue
    lab = Path(f"lab/smallcap/{sym}")
    cache.materialize(f"prices/{cache.safe(sym)}.csv", lab / "data" / f"{sym}.csv", None, START, None)
    for name, msym in {"VIX": "^VIX", "VIX3M": "^VIX3M", "SKEW": "^SKEW", "HYG": "HYG", "LQD": "LQD",
                       "SPY": "SPY", "IRX": "^IRX"}.items():
        cache.materialize(f"prices/{cache.safe(msym)}.csv", lab / "data" / f"{name}.csv", None, None, None)
    keep.append((sym, sector, str(first.date())))
    print(f"{sym}: ok ({sector}, from {first.date()})", flush=True)
pd.DataFrame(keep, columns=["symbol", "sector", "first_date"]).to_csv(a.out, index=False)
print(f"UNIVERSE: {len(keep)} of {N} sampled names kept")
