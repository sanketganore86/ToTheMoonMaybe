"""Pre-registered 2026-10-28, BEFORE any capex data was downloaded or looked at. Source: the user's observation
on the evening MSFT reported FY27 Q1 (capex $39.4B vs ~$50B expected, EPS beat, stock +4% after hours)."""
HYPOTHESIS = {
    "id": "E003",
    "statement": "For the AI-capex spenders (MSFT, GOOGL, AMZN, META), the earnings reaction gap depends on capex "
                 "and profit: when capex comes in BELOW its recent trend and EPS beats, the stock gaps UP; when "
                 "capex comes in ABOVE its trend, the stock gaps DOWN.",
    "rationale": "Since 2023 investors weigh the payback of AI data-center spending: lower-than-feared spending "
                 "plus higher profit means more free cash flow; a spending jump raises doubts about returns.",
    "events": "reports 2023-01-01 -> 2026-10-27 (tonight's MSFT report, which prompted the idea, is excluded); "
              "all four report after the close, so the reaction day is the next session",
    "capex": "quarterly purchases of property and equipment from SEC XBRL filings (year-to-date cash-flow values "
             "de-cumulated to quarters; AMZN: PaymentsToAcquireProductiveAssets)",
    "expected_capex": "trend proxy (consensus estimates are not available for free): previous quarter's capex x "
                      "(1 + mean quarter-over-quarter growth of the 4 quarters before it)",
    "groups": {"A (predict up)": "capex < expected AND EPS surprise > 0",
               "B (predict down)": "capex >= expected",
               "neither": "capex < expected AND EPS miss: no prediction, left out"},
    "outcome": "reaction-day gap: open / previous close - 1",
    "pass_criteria": {"mean_gap_A": "> 0", "mean_gap_B": "< 0",
                      "difference_A_minus_B": "> 0 with permutation p < 0.05 (10,000 shuffles of the A/B labels)",
                      "min_events_per_group": 8},
    "caveats": ["no split: the idea came from the user, not from this data, so all events form one test; but the "
                "user's sense of recent quarters is informed by them, so a pass is weaker evidence than E002",
                "small sample (~60 reports); the capex trend is only a proxy for analysts' expectations",
                "the gap happens overnight: an agent that is flat overnight cannot capture it"],
}
