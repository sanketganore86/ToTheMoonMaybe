# ToTheMoonMaybe

*A market hypothesis lab: to the moon, maybe; more often, the journal.*

Trading ideas tested like science experiments. Each idea is written down as a falsifiable
hypothesis **before** it is tested. It is tested **once** on data it has never seen, and the verdict is
recorded whether it passes or fails. Most ideas fail; the journals keep every one.

> **Research only. Not financial advice.** Nothing here recommends buying or selling anything,
> and nothing here trades real money. Past results, simulated or backtested, don't predict future
> ones. Option results are modeled, not real quotes.

## The first principle: protect capital

A strategy that might make money but can lose a lot counts as a failure here. Every test gets two
verdicts:
- **Edge:** is the signal better than chance out of sample?
- **Capital protection:** at the planned size, did any trade lose more than 2% of the account, or the
  account fall more than 10% from a peak, across the full history (2008 and 2020 included)?

A strategy is usable only if both pass.

## What's here

| Path | What it is |
|---|---|
| `.claude/skills/market-hypothesis-lab/` | The lab: scripts, the method (`SKILL.md`) and references (data sources, option modeling, idea families and past findings) |
| `lab/<TICKER>/hypotheses/` | Every hypothesis, pre-registered as code (`H###` position strategies, `T###` per-trade strategies, and others) |
| `lab/<TICKER>/JOURNAL.md` | Every test ever run on that ticker, pass or fail, with the interpretation |
| `lab/SUMMARY_TABLE.md` | All tests across tickers in one table |
| `lab/forecast/MODEL.md` | The frozen model behind the live forward test (predictions before the open, scored after the close) |
| `lab/paper*/agents/*/AGENT.md` | The pre-registered rules of each paper-trading agent |

Not here (kept private): downloaded market data, backtest outputs, the agents' daily records,
broker mirror records and outside trade calls. Market data re-downloads from the scripts.

## Quick start

You need [uv](https://docs.astral.sh/uv/) (it installs each script's Python dependencies itself).

```bash
S=.claude/skills/market-hypothesis-lab/scripts
uv run $S/cache.py status                                         # what is already downloaded
uv run $S/fetch_data.py AMD --lab lab/AMD --start 2004-01-01     # prices
uv run $S/sentiment.py fetch --lab lab/AMD                        # VIX, credit, SPY, rates
uv run $S/explore.py AMD --lab lab/AMD                            # in-sample statistics only
uv run $S/screen.py lab/AMD/hypotheses/H001_trend_ma200.py --lab lab/AMD
```

Data is cached machine-wide in `~/.cache/market-hypothesis-lab`. Every download goes through
`polite.py`, which rate-limits each provider. Please never bypass it. For SEC EDGAR, set
`SEC_USER_AGENT` to your own name and email first.

With [Claude Code](https://claude.com/claude-code), the lab loads as a skill when you open this
folder. Ask it to test an idea and it follows the method in `SKILL.md`.

## The loop

1. **Observe** the first 70% of history only. The last 30% is reserved for verdicts.
2. **Pre-register** the hypothesis as a file, with pass criteria fixed in advance.
3. **Screen** it on the two in-sample halves. This step is free and doesn't count as a test.
4. **Test once** out of sample. A changed idea is a new hypothesis with a new number.
5. **Interpret** the result in the journal, then pick the next idea from the evidence.

## Contributing

Ideas, hypotheses, fixes and replications on new tickers are welcome. Read
[CONTRIBUTING.md](CONTRIBUTING.md) first. The method's rules are what make the results trustworthy.

## License

[MIT](LICENSE).
