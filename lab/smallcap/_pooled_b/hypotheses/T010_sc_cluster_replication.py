from pathlib import Path
import pandas as pd
from sentiment import features

# Universe B: seeded sample (seed 7, 250 draws) of S&P 600 names NOT among the 100 drawn for
# universe A (seed 2026). Same filters (history from 2012). Fixed before any data was fetched.
_U = Path(__file__).resolve().parents[2] / "universe_b.csv"
TICKERS = pd.read_csv(_U)["symbol"].tolist()

HYPOTHESIS = {
    "tickers": TICKERS,
    "statement": "REPLICATION of T007 on a disjoint universe: buying when a 2nd+ distinct insider purchase "
                 "within 90 days becomes public, holding 20 sessions (stop -10%), earns a positive mean return "
                 "per trade, better than random 20-session holds. Identical rule and criteria; no tuning.",
    "rationale": "T007 on universe A: OOS +1.48%/trade vs +0.22% random (112 trades, p=0.10), consistent with "
                 "in-sample. A real effect must reappear on names never examined. Primary verdict: the standard "
                 "OOS window (2022+) on universe B, which is fresh in both names and time.",
    "instrument": "stock_long",
    "exit": {"take_profit": 0.50, "stop_loss": 0.10, "max_days": 20},
    "pass_criteria": {"max_p_value": 0.05, "min_trades": 30, "min_expectancy": 0.0, "max_worst_trade": -0.12},
}

def entries(df):
    f = features(None, df)
    b, n = f["insider_buy_90"], f["insider_buyers_90"]
    return ((b > b.shift(1)) & (n >= 2)).fillna(False)
