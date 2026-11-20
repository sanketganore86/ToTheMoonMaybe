from pathlib import Path
import pandas as pd
from sentiment import features

# the seeded random S&P 600 sample (build_universe.py, seed 2026); fixed before any test
_U = Path(__file__).resolve().parents[2] / "universe.csv"
TICKERS = pd.read_csv(_U)["symbol"].tolist()

HYPOTHESIS = {
    "tickers": TICKERS,
    "statement": "Small caps: selling a 30-day 0.25-delta cash-secured put at the next open after a new insider purchase is filed earns a positive mean account return per trade (+1% / -5% / 25 sessions), better than the same put on random days. MODELED options, wide spreads.",
    "rationale": "Small-cap replication of the large-cap rule (identical parameters). Universe: seeded random sample of current S&P 600 members with history from 2012 (survivorship-biased upward for every rule AND for the random baseline alike). Replicates T002. Small-cap options are thin: half-spread 12% of premium.",
    "instrument": "cash_secured_put",
    "params": {"dte": 30, "short_delta": 0.25, "allocation": 1.0, "spread_pct": 0.12},
    "exit": {"take_profit": 0.01, "stop_loss": 0.05, "max_days": 25},
    "pass_criteria": {"max_p_value": 0.05, "min_trades": 50, "min_expectancy": 0.0, "max_worst_trade": -0.10},
}

def entries(df):
    b = features(None, df)["insider_buy_90"]
    return (b > b.shift(1)).fillna(False)
