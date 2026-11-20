# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas>=2", "requests"]
# ///
"""Insider transactions for MANY companies from the SEC's quarterly Form 3/4/5 bulk data sets.

Per-filing downloads (alt_sentiment.py edgar) cost one request per Form 4: fine for a few
stocks, far too many for a universe. The SEC publishes the same data as one zip per quarter
for every company (2006 Q1 onward, ~14 MB each). This loader:
  - downloads each quarter once through polite.py (completed quarters never change, so they
    are cached forever; only the latest quarter is re-checked, at most once per --max-age)
  - keeps only open-market purchases (P) and sales (S) from Form 4 filings, in a compact
    gzip CSV per quarter in the central cache, and discards the zip
  - writes a lab's edgar_form4.csv in the same schema as alt_sentiment.py, so features()
    and every hypothesis work unchanged

Usage:
  uv run insider_bulk.py fetch --start 2010q1             # all quarters from 2010 (one-time ~1 GB)
  uv run insider_bulk.py extract SFNC --lab lab/smallcap/SFNC [--start 2010-01-01]
  uv run insider_bulk.py status
"""
import argparse
import io
import os
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import cache  # noqa: E402
from polite import request  # noqa: E402

UA = {"User-Agent": os.environ.get("SEC_USER_AGENT", "market-hypothesis-lab research script admin@example.com")}
PAGE = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
COLS = ["issuer_cik", "symbol", "owner", "officer", "director", "plan_10b5_1", "code", "shares", "price",
        "value", "filing_date", "accession"]


def _quarter_links():
    key = "edgar_bulk/_index"
    p = cache.path("edgar_bulk/_index.txt")
    if not (p.exists() and cache.is_fresh(key)):
        html = request("GET", PAGE, headers=UA).text
        links = sorted(set(re.findall(r'href="([^"]+?(\d{4}q\d)_form345\.zip)"', html)), key=lambda x: x[1])
        p.write_text("\n".join(f"{q} https://www.sec.gov{u}" for u, q in links))
        cache.mark_refreshed(key)
    return dict(line.split(" ", 1) for line in p.read_text().split("\n") if line)


def _parse(zbytes):
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    rd = lambda n, cols: pd.read_csv(z.open(n), sep="\t", dtype=str, usecols=cols, on_bad_lines="skip",
                                     quoting=3, encoding_errors="replace")
    sub = rd("SUBMISSION.tsv", ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK",
                                "ISSUERTRADINGSYMBOL"] + (["AFF10B5ONE"] if "AFF10B5ONE" in
                                pd.read_csv(z.open("SUBMISSION.tsv"), sep="\t", nrows=0).columns else []))
    sub = sub[sub["DOCUMENT_TYPE"] == "4"]
    tr = rd("NONDERIV_TRANS.tsv", ["ACCESSION_NUMBER", "TRANS_CODE", "TRANS_SHARES", "TRANS_PRICEPERSHARE"])
    tr = tr[tr["TRANS_CODE"].isin(["P", "S"])]
    own = rd("REPORTINGOWNER.tsv", ["ACCESSION_NUMBER", "RPTOWNERNAME", "RPTOWNER_RELATIONSHIP"])
    own = own.drop_duplicates("ACCESSION_NUMBER")  # first reporting owner per filing
    d = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER", how="left")
    rel = d["RPTOWNER_RELATIONSHIP"].fillna("")
    out = pd.DataFrame({
        "issuer_cik": d["ISSUERCIK"].astype(int),
        "symbol": d["ISSUERTRADINGSYMBOL"].str.upper().str.strip(),
        "owner": d["RPTOWNERNAME"],
        "officer": rel.str.contains("Officer", case=False),
        "director": rel.str.contains("Director", case=False),
        "plan_10b5_1": d.get("AFF10B5ONE", pd.Series("0", index=d.index)).isin(["1", "true", "TRUE"]),
        "code": d["TRANS_CODE"],
        "shares": pd.to_numeric(d["TRANS_SHARES"], errors="coerce"),
        "price": pd.to_numeric(d["TRANS_PRICEPERSHARE"], errors="coerce"),
        "filing_date": pd.to_datetime(d["FILING_DATE"], format="%d-%b-%Y", errors="coerce").dt.strftime("%Y-%m-%d"),
        "accession": d["ACCESSION_NUMBER"],
    })
    out["value"] = out["shares"] * out["price"]
    return out.dropna(subset=["filing_date"])[COLS]


def fetch(start="2010q1", max_age_h=cache.DEFAULT_MAX_AGE_H, refresh=False):
    links = _quarter_links()
    qs = [q for q in links if q >= start]
    latest = max(links)
    n_new = 0
    for q in qs:
        p = cache.path(f"edgar_bulk/{q}.csv.gz")
        key = f"edgar_bulk/{q}"
        complete = q != latest  # past quarters are final
        if p.exists() and (complete or (not refresh and cache.is_fresh(key, max_age_h))):
            continue
        r = request("GET", links[q], headers=UA)
        d = _parse(r.content)
        d.to_csv(p, index=False, compression="gzip")
        cache.mark_refreshed(key, rows=len(d))
        n_new += 1
        print(f"  {q}: {len(d):6} P/S transactions ({len(r.content) / 1e6:.0f} MB downloaded, zip discarded)", flush=True)
    print(f"Bulk insider data: {len(qs)} quarters from {start}, {n_new} downloaded now, rest from cache")


def ticker_cik(ticker):
    p = cache.path("edgar_bulk/company_tickers.json")
    if not (p.exists() and cache.is_fresh("edgar_bulk/company_tickers")):
        p.write_bytes(request("GET", "https://www.sec.gov/files/company_tickers.json", headers=UA).content)
        cache.mark_refreshed("edgar_bulk/company_tickers")
    import json
    for v in json.loads(p.read_text()).values():
        if v["ticker"].upper() == ticker.upper():
            return int(v["cik_str"])
    return None


def extract(ticker, lab, start=None, end=None):
    """Write <lab>/data/edgar_form4.csv for one ticker from the cached quarters (no download).
    Matches on the issuer CIK (stable across ticker changes), falling back to the symbol."""
    cik = ticker_cik(ticker)
    frames = []
    for p in sorted((cache.ROOT / "edgar_bulk").glob("*.csv.gz")):
        d = pd.read_csv(p, dtype={"symbol": str})
        frames.append(d[(d.issuer_cik == cik) if cik else (d.symbol == ticker.upper())])
    d = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLS)
    if start:
        d = d[d.filing_date >= start]
    if end:
        d = d[d.filing_date <= end]
    out = Path(lab) / "data" / "edgar_form4.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    d.drop(columns=["issuer_cik", "symbol"]).sort_values("filing_date").to_csv(out, index=False)
    return len(d), int((d.code == "P").sum())


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch"); f.add_argument("--start", default="2010q1")
    f.add_argument("--refresh", action="store_true"); f.add_argument("--max-age", type=float, default=cache.DEFAULT_MAX_AGE_H)
    e = sub.add_parser("extract"); e.add_argument("ticker"); e.add_argument("--lab", required=True)
    e.add_argument("--start"); e.add_argument("--end")
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(a.start, a.max_age, a.refresh)
    elif a.cmd == "extract":
        n, buys = extract(a.ticker, a.lab, a.start, a.end)
        print(f"{a.ticker}: {n} insider transactions ({buys} open-market buys) -> {a.lab}/data/edgar_form4.csv")
    else:
        qs = sorted((cache.ROOT / "edgar_bulk").glob("*.csv.gz"))
        print(f"{len(qs)} quarters cached" + (f": {qs[0].name[:6]} .. {qs[-1].name[:6]}" if qs else ""))


if __name__ == "__main__":
    main()
