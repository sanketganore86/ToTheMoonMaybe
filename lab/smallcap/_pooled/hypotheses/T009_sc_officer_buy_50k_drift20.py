from pathlib import Path
import pandas as pd
from sentiment import features

# the seeded random S&P 600 sample (build_universe.py, seed 2026); fixed before any test
_U = Path(__file__).resolve().parents[2] / "universe.csv"
TICKERS = pd.read_csv(_U)["symbol"].tolist()

HYPOTHESIS = {
    "tickers": TICKERS,
    "statement": "Small caps: buying at the next open after an OFFICER files an open-market purchase worth at least $50,000, holding 20 sessions (stop -10%), earns a positive mean return per trade, better than random 20-session holds.",
    "rationale": "Small-cap replication of the large-cap rule (identical parameters). Universe: seeded random sample of current S&P 600 members with history from 2012 (survivorship-biased upward for every rule AND for the random baseline alike). Literature: purchases by officers (who know operations best) and of meaningful size carry more information than token director buys.",
    "instrument": "stock_long",
    "exit": {"take_profit": 0.50, "stop_loss": 0.10, "max_days": 20},
    "pass_criteria": {"max_p_value": 0.05, "min_trades": 30, "min_expectancy": 0.0, "max_worst_trade": -0.12},
}

def entries(df):
    e = pd.read_csv(Path(df.attrs["lab"]) / "data" / "edgar_form4.csv", parse_dates=["filing_date"])
    e = e[(e.code == "P") & (e.officer.astype(str) == "True")]
    big = e.groupby("filing_date")["value"].sum()
    big = big[big >= 50_000]
    avail = (big.index + pd.tseries.offsets.BDay(1))  # usable from the next session
    return pd.Series(df.index.isin(avail), index=df.index)
