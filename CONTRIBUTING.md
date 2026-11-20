# Contributing

Thanks for helping. This lab's value is that its results can be trusted, so contributions follow
the method strictly. All changes arrive as pull requests; the maintainer reviews and merges every one.

## How to contribute

1. **Fork** this repo and create a branch (`hyp/AMD-H006-gap-fade`, `fix/screen-split`, ...).
2. Make your change, following the rules below.
3. Open a pull request against `main` and fill in the template.
4. Expect questions. A hypothesis PR is reviewed **before** its out-of-sample test is run, so
   submit it pre-registered and untested (see below).

## Rules for hypotheses

- **Pre-register first.** Add the hypothesis file (`lab/<TICKER>/hypotheses/H###_slug.py` or
  `T###_slug.py`, next free number) with its `statement`, `rationale` and `pass_criteria`, and
  open the PR **before** running `backtest.py` or `trade_backtest.py`. You may run `explore.py`
  and `screen.py`; they only look at in-sample data.
- **One test, one verdict.** Never edit a hypothesis after seeing its out-of-sample result and
  re-run it under the same ID. A variant is a new hypothesis with a new number.
- **Journals are append-only.** Never delete or rewrite a past entry, including failures.
- **No lookahead.** Use only `rolling`, `shift(+n)` and expanding windows. Never use `shift(-n)`,
  full-sample statistics or `center=True`. The engines check this and mark violations invalid.
- **Capital protection is a verdict, not a footnote.** Report the worst trade, the drawdown and the
  safe size, never a return alone.
- **Simple and mechanistic.** Few parameters, round numbers, and a reason why it might work.

## Rules for code

- Every network call goes through `polite.py`. Never raise its rate limits.
- Never commit data, results, charts, API keys or credentials (`.gitignore` covers the usual paths).
- Keep scripts runnable with `uv run` (dependencies declared in the script header).
- No real-money trading code and no unofficial broker APIs.
- Workflow files (`.github/workflows/`) are not accepted from forks.

## What not to send

- Trade recommendations, signals for real money or anything framed as financial advice.
- Other people's paid or copyrighted content (alert services, newsletters, chart screenshots).
- Personal data of any kind.

By contributing you agree that your contribution is licensed under the MIT License of this repo.
