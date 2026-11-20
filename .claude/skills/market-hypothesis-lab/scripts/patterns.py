"""Candlestick pattern detectors. Every function returns a boolean Series that is True on
the bar where the pattern COMPLETES, using that bar and earlier bars only (no lookahead),
so a hypothesis can use them directly:  `from patterns import bullish_engulfing`.
"""
import pandas as pd


def _parts(df):
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    body = (c - o).abs()
    rng = (h - l).replace(0, float("nan"))
    upper = h - pd.concat([o, c], axis=1).max(axis=1)
    lower = pd.concat([o, c], axis=1).min(axis=1) - l
    return o, h, l, c, body, rng, upper, lower


def downtrend(df, n=5):
    return df["Close"] < df["Close"].shift(n)


def uptrend(df, n=5):
    return df["Close"] > df["Close"].shift(n)


def doji(df):
    o, h, l, c, body, rng, up, lo = _parts(df)
    return body <= 0.1 * rng


def hammer(df):
    """Long lower wick, small upper wick, after a short-term decline (bullish reversal)."""
    o, h, l, c, body, rng, up, lo = _parts(df)
    return (lo >= 2 * body) & (up <= 0.25 * rng) & (body > 0.05 * rng) & downtrend(df)


def shooting_star(df):
    """Long upper wick, small lower wick, after a short-term rise (bearish reversal)."""
    o, h, l, c, body, rng, up, lo = _parts(df)
    return (up >= 2 * body) & (lo <= 0.25 * rng) & (body > 0.05 * rng) & uptrend(df)


def bullish_engulfing(df):
    o, c = df["Open"], df["Close"]
    po, pc = o.shift(1), c.shift(1)
    return (pc < po) & (c > o) & (o <= pc) & (c >= po) & downtrend(df)


def bearish_engulfing(df):
    o, c = df["Open"], df["Close"]
    po, pc = o.shift(1), c.shift(1)
    return (pc > po) & (c < o) & (o >= pc) & (c <= po) & uptrend(df)


def three_white_soldiers(df):
    o, c = df["Open"], df["Close"]
    g = c > o
    return g & g.shift(1, fill_value=False) & g.shift(2, fill_value=False) & (c > c.shift(1)) & (c.shift(1) > c.shift(2))


def three_black_crows(df):
    o, c = df["Open"], df["Close"]
    r = c < o
    return r & r.shift(1, fill_value=False) & r.shift(2, fill_value=False) & (c < c.shift(1)) & (c.shift(1) < c.shift(2))


def gap_up(df):
    return df["Open"] > df["High"].shift(1)


def gap_down(df):
    return df["Open"] < df["Low"].shift(1)


def inside_bar(df):
    return (df["High"] < df["High"].shift(1)) & (df["Low"] > df["Low"].shift(1))


ALL = {
    "doji": doji, "hammer": hammer, "shooting_star": shooting_star,
    "bullish_engulfing": bullish_engulfing, "bearish_engulfing": bearish_engulfing,
    "three_white_soldiers": three_white_soldiers, "three_black_crows": three_black_crows,
    "gap_up": gap_up, "gap_down": gap_down, "inside_bar": inside_bar,
}
