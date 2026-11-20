# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "numpy", "requests"]
# ///
"""Free historical, point-in-time sentiment beyond market prices.

  edgar  SEC EDGAR Form 4 insider transactions (full history). Open-market purchases (code P)
         are the informative signal; sales (S) are often scheduled (10b5-1) and noisy.
  finra  FINRA consolidated short interest, twice monthly (Dec 2017 onward).
  gdelt  GDELT 2.0 news tone and article volume for a company-name query (2017 onward).

Everything is cached machine-wide (cache.py): reruns download only what is new, nothing at
all while the cache is fresh (--max-age, default 20 h), and --start/--end filter what is
fetched (EDGAR) and what is copied into the lab.

Usage (each writes to <lab>/data/; EDGAR resumes where it stopped):
  uv run alt_sentiment.py edgar AXP --lab lab/AXP
  uv run alt_sentiment.py finra AXP --lab lab/AXP
  uv run alt_sentiment.py gdelt AXP --lab lab/AXP --query '"American Express"'

All HTTP goes through polite.py: per-host minimum intervals shared across processes, daily
caps, Retry-After / exponential backoff on 429/503, and a circuit breaker. Never bypass it.
SEC requires a User-Agent with a contact; set SEC_USER_AGENT="Your Name you@example.com".

Point-in-time rules applied in alt_features():
  - insider data is keyed on the FILING date and used from the next session on
  - short interest is used from settlement date + 10 business days (FINRA publishes ~7-8 later)
  - GDELT days are UTC (they end ~8pm ET, after the close), so news is used from the next session
"""
import argparse
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from polite import PoliteGiveUp, request  # noqa: E402
import cache  # noqa: E402

UA = os.environ.get("SEC_USER_AGENT", "market-hypothesis-lab research script admin@example.com")
SEC = {"User-Agent": UA}


# ---------------------------------------------------------------- EDGAR
def _cik(ticker):
    j = request("GET", "https://www.sec.gov/files/company_tickers.json", headers=SEC).json()
    for v in j.values():
        if v["ticker"].upper() == ticker.upper():
            return int(v["cik_str"])
    raise SystemExit(f"CIK not found for {ticker}")


def _form4_index(cik, recent_only=False):
    """recent_only: the newest ~1000 filings suffice for an incremental update."""
    sub = request("GET", f"https://data.sec.gov/submissions/CIK{cik:010d}.json", headers=SEC).json()
    frames = [pd.DataFrame(sub["filings"]["recent"])]
    for f in ([] if recent_only else sub["filings"].get("files", [])):
        frames.append(pd.DataFrame(request("GET", f"https://data.sec.gov/submissions/{f['name']}", headers=SEC).json()))
    idx = pd.concat(frames, ignore_index=True)
    return idx[idx["form"] == "4"][["accessionNumber", "filingDate", "primaryDocument"]]


def _txt(node, path):
    el = node.find(path)
    return el.text.strip() if el is not None and el.text else None


def _parse_form4(xml_bytes):
    root = ET.fromstring(xml_bytes)
    rel = root.find("reportingOwner/reportingOwnerRelationship")
    owner = _txt(root, "reportingOwner/reportingOwnerId/rptOwnerName")
    is_officer = rel is not None and _txt(rel, "isOfficer") in ("1", "true")
    is_director = rel is not None and _txt(rel, "isDirector") in ("1", "true")
    plan = _txt(root, "aff10b5One") in ("1", "true")
    rows = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _txt(t, "transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        try:
            sh = float(_txt(t, "transactionAmounts/transactionShares/value") or 0)
            px = float(_txt(t, "transactionAmounts/transactionPricePerShare/value") or 0)
        except ValueError:
            continue
        rows.append({"owner": owner, "officer": is_officer, "director": is_director,
                     "plan_10b5_1": plan, "code": code, "shares": sh, "price": px, "value": sh * px})
    return rows


def fetch_edgar(ticker, lab, start="2005-01-01", end=None, refresh=False, max_age_h=None):
    """Insider Form 4s into the central cache (incremental: only filings not yet fetched),
    then a [start, end] copy into the lab."""
    tk = ticker.upper()
    rel, key = f"edgar/{tk}/form4.csv", f"edgar/{tk}/form4"
    out, done = cache.path(rel), cache.path(f"edgar/{tk}/done.txt")
    max_age_h = cache.DEFAULT_MAX_AGE_H if max_age_h is None else max_age_h
    if out.exists() and not refresh and cache.is_fresh(key, max_age_h):
        print(f"{tk}: insider cache fresh, no download", flush=True)
        return _edgar_to_lab(tk, lab, start, end)
    seen = set(done.read_text().split()) if done.exists() else set()
    covered = cache.get_info(key).get("covered_from")
    if out.exists() and not covered:  # seeded from a lab: infer coverage from the data itself
        fd = pd.read_csv(out, usecols=["filing_date"])["filing_date"]
        covered = fd.min() if len(fd) else start
    backfill = covered is None or start < covered
    cik = _cik(tk)
    idx = _form4_index(cik, recent_only=bool(seen) and not backfill)
    sel = idx["filingDate"] >= start
    if end:
        sel &= idx["filingDate"] <= end
    idx = idx[sel & ~idx["accessionNumber"].isin(seen)]
    print(f"{tk}: CIK {cik}, {len(idx)} new Form 4 filings to fetch", flush=True)
    buf, n = [], 0

    def flush():
        nonlocal buf
        if buf:
            pd.DataFrame(buf).to_csv(out, mode="a", header=not out.exists(), index=False)
            buf = []
        done.write_text("\n".join(sorted(seen)))

    try:
        for _, f in idx.iterrows():
            acc = f["accessionNumber"].replace("-", "")
            doc = f["primaryDocument"].split("/")[-1]
            try:
                rows = _parse_form4(request("GET", f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}",
                                            headers=SEC).content)
            except PoliteGiveUp:
                raise
            except Exception as e:  # malformed or missing XML: skip, but remember it
                rows = []
                print("  skip", f["accessionNumber"], str(e)[:60], flush=True)
            for r in rows:
                r["filing_date"] = f["filingDate"]
                r["accession"] = f["accessionNumber"]
            buf += rows
            seen.add(f["accessionNumber"])
            n += 1
            if n % 50 == 0 or n == len(idx):
                flush()
                print(f"  {n}/{len(idx)}", flush=True)
    except PoliteGiveUp as e:
        flush()
        raise SystemExit(f"Stopped politely: {e}. Progress saved in the cache; rerun later to resume.")
    flush()
    if not out.exists():
        pd.DataFrame(columns=["owner", "officer", "director", "plan_10b5_1", "code", "shares", "price",
                              "value", "filing_date", "accession"]).to_csv(out, index=False)
    cache.mark_refreshed(key, covered_from=min(start, covered or start))
    return _edgar_to_lab(tk, lab, start, end)


def _edgar_to_lab(tk, lab, start, end):
    dst = Path(lab) / "data" / "edgar_form4.csv"
    cache.materialize(f"edgar/{tk}/form4.csv", dst, "filing_date", start, end)
    n = max(sum(1 for _ in open(dst)) - 1, 0)
    print(f"Saved {dst} ({n} transactions, filed {start} -> {end or 'today'})", flush=True)


# ---------------------------------------------------------------- FINRA
def fetch_finra(ticker, lab, start=None, end=None, refresh=False, max_age_h=None):
    """Whole history in one request; skipped while the cache is fresh (FINRA publishes twice a month)."""
    tk = ticker.upper()
    rel, key = f"finra/{tk}.csv", f"finra/{tk}"
    p = cache.path(rel)
    max_age_h = cache.DEFAULT_MAX_AGE_H if max_age_h is None else max_age_h
    if p.exists() and not refresh and cache.is_fresh(key, max_age_h):
        print(f"{tk}: short-interest cache fresh, no download", flush=True)
    else:
        url = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"
        body = {"limit": 5000, "fields": ["settlementDate", "currentShortPositionQuantity", "averageDailyVolumeQuantity",
                                          "daysToCoverQuantity", "changePercent"],
                "compareFilters": [{"compareType": "equal", "fieldName": "symbolCode", "fieldValue": tk}]}
        r = request("POST", url, json=body, headers={"Accept": "application/json"})
        df = pd.DataFrame(r.json()).sort_values("settlementDate").drop_duplicates("settlementDate", keep="last")
        df.to_csv(p, index=False)
        cache.mark_refreshed(key)
    out = Path(lab) / "data" / "finra_short_interest.csv"
    cache.materialize(rel, out, "settlementDate", start, end)
    d = pd.read_csv(out)
    print(f"Saved {out} ({len(d)} rows, {d.settlementDate.iloc[0]} -> {d.settlementDate.iloc[-1]})", flush=True)


# ---------------------------------------------------------------- GDELT
def fetch_gdelt(ticker, lab, query, start_year=2017, start=None, end=None, refresh=False, max_age_h=None):
    """2 requests per ticker the first time; afterwards only the days since the last cached
    date (with a 7-day overlap, GDELT revises recent days)."""
    tk = ticker.upper()
    rel, key = f"gdelt/{tk}.csv", f"gdelt/{tk}"
    p = cache.path(rel)
    max_age_h = cache.DEFAULT_MAX_AGE_H if max_age_h is None else max_age_h
    info = cache.get_info(key)
    if info.get("query") not in (None, query):
        print(f"{tk}: query changed ({info.get('query')} -> {query}); refetching full range", flush=True)
        p.unlink(missing_ok=True)
    if p.exists() and not refresh and cache.is_fresh(key, max_age_h):
        print(f"{tk}: news cache fresh, no download", flush=True)
    else:
        since = f"{start_year}0101000000"
        if p.exists():
            last = pd.read_csv(p, parse_dates=["date"])["date"].max()
            since = (last - pd.Timedelta(days=7)).strftime("%Y%m%d000000")
        until = pd.Timestamp.today().strftime("%Y%m%d235959")
        series = {}
        for mode, col in (("timelinetone", "tone"), ("timelinevolraw", "volume")):
            params = {"query": query, "mode": mode, "format": "json", "startdatetime": since, "enddatetime": until}
            data = request("GET", "https://api.gdeltproject.org/api/v2/doc/doc", params=params).json()["timeline"][0]["data"]
            series[col] = pd.Series({pd.Timestamp(d["date"][:8]): d["value"] for d in data}, dtype=float)
        g = pd.DataFrame(series).rename_axis("date").reset_index()
        cache.merge_csv(p, g, date_col="date")
        cache.mark_refreshed(key, query=query)
        print(f"{tk}: fetched news from {since[:8]} ({len(g)} days)", flush=True)
    out = Path(lab) / "data" / "gdelt_news.csv"
    cache.materialize(rel, out, "date", start, end)
    g = pd.read_csv(out, parse_dates=["date"])
    print(f"Saved {out} ({len(g)} days, {g.date.min().date()} -> {g.date.max().date()})", flush=True)


# ---------------------------------------------------------------- features
def alt_features(lab, df):
    """Daily features aligned to df.index (NaN where a source is missing). No lookahead."""
    lab = Path(lab)
    idx = df.index
    f = pd.DataFrame(index=idx)
    bday = pd.tseries.offsets.BDay

    p = lab / "data" / "edgar_form4.csv"
    if p.exists():
        e = pd.read_csv(p, parse_dates=["filing_date"])
        e["avail"] = e["filing_date"] + bday(1)
        cal = pd.date_range(min(idx[0], e["avail"].min() if len(e) else idx[0]), idx[-1], freq="D")
        buy = e[e.code == "P"].groupby("avail")["value"].sum().reindex(cal, fill_value=0)
        sell = e[(e.code == "S") & ~e.plan_10b5_1.astype(bool)].groupby("avail")["value"].sum().reindex(cal, fill_value=0)
        nbuyers = e[e.code == "P"].groupby("avail")["owner"].nunique().reindex(cal, fill_value=0)
        b90, s90 = buy.rolling(90).sum(), sell.rolling(90).sum()
        f["insider_buy_90"] = b90.reindex(idx)
        f["insider_buyers_90"] = nbuyers.rolling(90).sum().reindex(idx)
        f["insider_net_90"] = ((b90 - s90) / (b90 + s90).replace(0, np.nan)).reindex(idx)
        f["insider_sell_90"] = s90.reindex(idx)

    p = lab / "data" / "finra_short_interest.csv"
    if p.exists():
        s = pd.read_csv(p, parse_dates=["settlementDate"])
        s["avail"] = s["settlementDate"] + bday(10)
        s = s.set_index("avail").sort_index()
        dtc = s["daysToCoverQuantity"].astype(float)
        si = s["currentShortPositionQuantity"].astype(float)
        part = pd.DataFrame({
            "short_dtc": dtc,
            "short_dtc_z": (dtc - dtc.rolling(24, min_periods=12).mean()) / dtc.rolling(24, min_periods=12).std(),
            "short_chg_3m": si / si.shift(6) - 1,  # ~3 months of twice-monthly reports
        })
        f = f.join(part.reindex(part.index.union(idx)).ffill().reindex(idx))

    p = lab / "data" / "gdelt_news.csv"
    if p.exists():
        g = pd.read_csv(p, parse_dates=["date"]).set_index("date").sort_index()
        g.index = g.index + pd.Timedelta(days=1)  # UTC day ends after the US close -> use next session
        tone, vol = g["tone"], g["volume"]
        part = pd.DataFrame({
            "news_tone": tone,
            "news_tone_7": tone.rolling(7, min_periods=3).mean(),
            "news_tone_z": (tone.rolling(7, min_periods=3).mean() - tone.rolling(180, min_periods=60).mean())
                           / tone.rolling(180, min_periods=60).std(),
            "news_vol_z": (np.log1p(vol) - np.log1p(vol).rolling(90, min_periods=30).mean())
                          / np.log1p(vol).rolling(90, min_periods=30).std(),
        })
        f = f.join(part.reindex(part.index.union(idx)).ffill(limit=4).reindex(idx))
    return f


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("edgar", "finra", "gdelt"):
        s = sub.add_parser(c)
        s.add_argument("ticker")
        s.add_argument("--lab", required=True)
        s.add_argument("--start", default="2005-01-01" if c == "edgar" else None,
                       help="first date to fetch (edgar) / copy into the lab")
        s.add_argument("--end", default=None, help="last date to fetch (edgar) / copy into the lab")
        s.add_argument("--refresh", action="store_true", help="check for new data even if the cache is fresh")
        s.add_argument("--max-age", type=float, default=None, help="hours a cached copy counts as fresh (default 20)")
        if c == "gdelt":
            s.add_argument("--query", required=True, help='e.g. \'"American Express"\'')
            s.add_argument("--start-year", type=int, default=2017)
    a = ap.parse_args()
    (Path(a.lab) / "data").mkdir(parents=True, exist_ok=True)
    kw = dict(start=a.start, end=a.end, refresh=a.refresh, max_age_h=a.max_age)
    if a.cmd == "edgar":
        fetch_edgar(a.ticker, a.lab, **kw)
    elif a.cmd == "finra":
        fetch_finra(a.ticker, a.lab, **kw)
    else:
        fetch_gdelt(a.ticker, a.lab, a.query, a.start_year, **kw)


if __name__ == "__main__":
    main()
