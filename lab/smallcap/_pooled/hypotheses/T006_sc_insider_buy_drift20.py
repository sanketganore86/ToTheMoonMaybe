from pathlib import Path
import pandas as pd
from sentiment import features

# the seeded random S&P 600 sample (build_universe.py, seed 2026); fixed before any test
_U = Path(__file__).resolve().parents[2] / "universe.csv"
TICKERS = pd.read_csv(_U)["symbol"].tolist()

HYPOTHESIS = {
    "tickers": TICKERS,
    "statement": "Small caps: buying at the next open after a new insider open-market purchase is filed and holding 20 sessions (stop -10%, no target) earns a positive mean return per trade, better than random 20-session holds.",
    "rationale": "Small-cap replication of the large-cap rule (identical parameters). Universe: seeded random sample of current S&P 600 members with history from 2012 (survivorship-biased upward for every rule AND for the random baseline alike). Replicates T003 (post-filing drift).",
    "instrument": "stock_long",
    "exit": {"take_profit": 0.50, "stop_loss": 0.10, "max_days": 20},
    "pass_criteria": {"max_p_value": 0.05, "min_trades": 50, "min_expectancy": 0.0, "max_worst_trade": -0.12},
}

def entries(df):
    b = features(None, df)["insider_buy_90"]
    return (b > b.shift(1)).fillna(False)
