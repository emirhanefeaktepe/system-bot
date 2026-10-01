"""Teknik göstergeler. Hepsi yalnızca o güne kadarki veriyi kullanır (geleceğe bakmaz)."""
from __future__ import annotations

import pandas as pd


def _rsi(c: pd.Series, n: int) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, 1e-12)
    return 100 - 100 / (1 + rs)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c, h, l = df["close"], df["high"], df["low"]
    for n in (5, 20, 50, 100, 200):
        df[f"sma{n}"] = c.rolling(n).mean()
    df["rsi14"] = _rsi(c, 14)
    df["rsi3"] = _rsi(c, 3)
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df["macd_h"] = macd - macd.ewm(span=9, adjust=False).mean()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["atr14"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    df["high20"] = h.rolling(20).max().shift(1)       # önceki 20 günün zirvesi
    df["low20"] = l.rolling(20).min().shift(1)
    df["vol20"] = df["volume"].rolling(20).mean().shift(1)
    df["vol_ratio"] = df["volume"] / df["vol20"].replace(0, float("nan"))
    df["roc63"] = c.pct_change(63, fill_method=None) * 100
    df["roc126"] = c.pct_change(126, fill_method=None) * 100
    df["chg1"] = c.pct_change(fill_method=None) * 100
    return df


def build(data: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Her hisseye göstergeleri ekler ve momentum sıralamalarını (1 = en güçlü) hesaplar."""
    frames = {t: add_indicators(df) for t, df in data.items()}
    ranks = {}
    for col in ("roc63", "roc126"):
        wide = pd.DataFrame({t: f[col] for t, f in frames.items()})
        ranks[col] = wide.rank(axis=1, ascending=False, method="min")
    return frames, ranks
