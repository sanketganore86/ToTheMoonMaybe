# Data sources

All are free, historical and point-in-time. All are fetched through `polite.py`.

| Source | Script | History | Features (columns from `sentiment.features`) | Point-in-time rule |
|---|---|---|---|---|
| Yahoo daily OHLCV | `fetch_data.py` | full | prices | adjusted closes |
| VIX, VIX3M, SKEW, HYG, LQD, SPY | `sentiment.py fetch` | 2005+ (VIX3M 2006, HYG 2007) | `vix, vix_z, vix_spike, term, skew, credit, spy_trend` | close of the day |
| Stock volume / opens | (prices) | full | `attention, gap` | same day |
| SEC EDGAR Form 4 | `alt_sentiment.py edgar` | full | `insider_buy_90, insider_buyers_90, insider_net_90, insider_sell_90` | filing date + 1 business day; 10b5-1 planned sales excluded from sells |
| FINRA short interest | `alt_sentiment.py finra` | Dec 2017+ (twice monthly) | `short_dtc, short_dtc_z, short_chg_3m` | settlement + 10 business days |
| GDELT 2.0 news | `alt_sentiment.py gdelt` | 2017+ | `news_tone, news_tone_7, news_tone_z, news_vol_z` | next session (UTC day ends after the close) |
| ^IRX T-bill rate | `sentiment.py fetch` (included) | full | used by the option model | close of the day |
| Cboe PUT index, ^GSPC | `fetch_data.py ^PUT` and `^GSPC` (once) | 2007+ | option-model validation only | n/a |

Caching
- All sources are stored once in the machine-wide cache (`cache.py`). Labs receive filtered
  copies. Freshness is tracked per item in `meta.json`. Incremental update rules:
  prices re-fetch from the last cached day − 7 (a full re-download happens automatically
  if a split or dividend changed the adjusted history); EDGAR fetches only filings not yet
  in `done.txt` and reads only the recent filing index once the history is cached; GDELT
  re-fetches from the last cached day − 7 (it revises recent days); FINRA is one request.
- Data that predates the cache sitting in lab folders can be imported with `cache.py seed --labs lab`.

Notes
- EDGAR: one request per Form 4. Large caps have 1,000–5,000 filings, so expect 10–40
  minutes per company at 2 requests per second. Progress is saved every 50 filings and
  resumes automatically.
- GDELT: 2 requests per ticker (tone and volume over the whole range). It returns HTTP 429
  readily, and `polite.py` backs off for minutes. Use unambiguous queries: `"Visa Inc"`,
  `"Alphabet Inc"`, not `Visa` or `Google`.
- FINRA's API returns a symbol's whole history in one request.
- Not available for free: historical put/call ratios (Yahoo removed them), AAII survey
  (HTTP 403), social or news sentiment scores with deep history, historical option chains.
  Broker accounts (Robinhood, Fidelity) do not offer historical sentiment APIs.
- For features that start in 2017–18, add `"start"` to the hypothesis so the 70/30 split
  applies within the window where the data exists.
