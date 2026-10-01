"""Fiyat verisi: Yahoo Finance (BIST, ~15 dk gecikmeli) ve test için sentetik veri."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

import config

COLS = ["open", "high", "low", "close", "volume"]


def yahoo_symbol(t: str) -> str:
    return f"{t}.IS"


def now_tr() -> pd.Timestamp:
    return pd.Timestamp.now(tz=config.TZ)


def _pick(raw: pd.DataFrame, sym: str) -> pd.DataFrame | None:
    if raw is None or raw.empty:
        return None
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw
    for lvl in (0, 1):
        if sym in raw.columns.get_level_values(lvl):
            return raw.xs(sym, axis=1, level=lvl)
    return None


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=lambda c: str(c).lower())
    df = df[[c for c in COLS if c in df.columns]].dropna(subset=["close"])
    df = df[df["close"] > 0]
    return df.astype(float)


def load_daily(tickers: list[str], period: str = config.HISTORY_PERIOD) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    syms = [yahoo_symbol(t) for t in tickers]
    raw = yf.download(syms, period=period, interval="1d", auto_adjust=False,
                      group_by="ticker", progress=False, threads=True)
    out: dict[str, pd.DataFrame] = {}
    for t, s in zip(tickers, syms):
        df = _pick(raw, s)
        if df is None:
            continue
        df = _clean(df)
        idx = pd.to_datetime(df.index)
        if idx.tz is not None:
            idx = idx.tz_convert(config.TZ).tz_localize(None)
        df.index = idx.normalize()
        df = df[~df.index.duplicated(keep="last")]
        if len(df) >= 30:
            out[t] = df
    return out


def load_intraday(tickers: list[str]) -> dict[str, dict]:
    """Bugünün 15 dakikalık çubuklarından son fiyat, gün içi en yüksek/en düşük, açılış ve dünkü kapanış."""
    import yfinance as yf

    syms = [yahoo_symbol(t) for t in tickers]
    raw = yf.download(syms, period="5d", interval="15m", auto_adjust=False,
                      group_by="ticker", progress=False, threads=True)
    today = now_tr().date()
    out: dict[str, dict] = {}
    for t, s in zip(tickers, syms):
        df = _pick(raw, s)
        if df is None:
            continue
        df = _clean(df)
        if df.empty:
            continue
        idx = pd.to_datetime(df.index)
        idx = idx.tz_localize("UTC") if idx.tz is None else idx
        df.index = idx.tz_convert(config.TZ)
        quote = summarize_intraday(df, today)
        if quote:
            out[t] = quote
    return out


def summarize_intraday(df: pd.DataFrame, today: dt.date) -> dict | None:
    dates = df.index.date
    d = df[dates == today]
    if d.empty:
        return None
    prev = df[dates < today]
    return {
        "last": float(d["close"].iloc[-1]),
        "open": float(d["open"].iloc[0]),
        "high": float(d["high"].max()),
        "low": float(d["low"].min()),
        "prev_close": float(prev["close"].iloc[-1]) if not prev.empty else None,
        "time": d.index[-1].strftime("%H:%M"),
    }


# ---------------------------------------------------------------- test verisi

def synthetic_daily(tickers: list[str], n: int = 750, end: dt.date | None = None,
                    seed: int = 7) -> dict[str, pd.DataFrame]:
    """Gerçek olmayan, rastgele fiyat serileri. Yalnızca kodu denemek için."""
    end = end or now_tr().date()
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=n)
    out = {}
    for i, t in enumerate(tickers):
        rng = np.random.default_rng(seed + i)
        drift = rng.normal(0.0006, 0.0008)
        vol = rng.uniform(0.014, 0.03)
        regime = np.sin(np.linspace(0, rng.uniform(2, 6), n)) * 0.0015
        ret = rng.normal(drift + regime, vol)
        close = rng.uniform(8, 60) * np.exp(np.cumsum(ret))
        opn = close * (1 + rng.normal(0, vol / 3, n))
        high = np.maximum(opn, close) * (1 + np.abs(rng.normal(0, vol / 2, n)))
        low = np.minimum(opn, close) * (1 - np.abs(rng.normal(0, vol / 2, n)))
        volume = rng.lognormal(15, 0.4, n)
        out[t] = pd.DataFrame({"open": opn, "high": high, "low": low,
                               "close": close, "volume": volume}, index=idx)
    return out


def synthetic_intraday(daily: dict[str, pd.DataFrame], seed: int = 11) -> dict[str, dict]:
    rng = np.random.default_rng(seed)
    out = {}
    for t, df in daily.items():
        prev = float(df["close"].iloc[-1])
        opn = prev * (1 + rng.normal(0, 0.008))
        path = opn * np.exp(np.cumsum(rng.normal(0, 0.006, 20)))
        out[t] = {"last": float(path[-1]), "open": opn, "high": float(max(path.max(), opn)),
                  "low": float(min(path.min(), opn)), "prev_close": prev, "time": "14:30"}
    return out
