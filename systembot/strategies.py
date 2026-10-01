"""Beş vadeli strateji. Her biri kendi 1.000 TL'lik bölmesinde ayrı işlem yapar,
böylece hangi vadenin gerçekten işe yaradığı ayrı ayrı ölçülür."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import pandas as pd


@dataclass
class Signal:
    ticker: str
    strategy: str
    price: float
    stop: float
    target: float | None
    max_days: int
    score: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def ok(*vals) -> bool:
    return all(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in vals)


class Strategy:
    key = ""
    name = ""
    horizon = ""
    max_days = 0
    about = ""

    def entry(self, t: str, row: pd.Series, prev: pd.Series, rank: dict) -> Signal | None:
        raise NotImplementedError

    def exit_on_close(self, pos: dict, row: pd.Series) -> str | None:
        return None

    def _sig(self, t, row, stop, target, score, reason) -> Signal:
        return Signal(t, self.key, float(row["close"]), round(float(stop), 2),
                      None if target is None else round(float(target), 2),
                      self.max_days, round(float(score), 3), reason)


class ShortBounce(Strategy):
    key, name, horizon, max_days = "h5", "Kısa vadeli tepki", "1 hafta", 5
    about = "Yükseliş trendindeki hissede 2-3 günlük sert düşüşten sonra tepki alımı."

    def entry(self, t, row, prev, rank):
        if not ok(row.sma50, row.sma100, row.rsi3, row.atr14):
            return None
        if row.close > row.sma50 > row.sma100 and row.rsi3 < 15:
            return self._sig(t, row, row.close - 2 * row.atr14, row.close + 2 * row.atr14,
                             15 - row.rsi3, f"Trend yukarı, RSI(3) {row.rsi3:.0f} ile aşırı satımda")
        return None

    def exit_on_close(self, pos, row):
        return "Tepki geldi (5 günlük ortalamanın üstü)" if ok(row.sma5) and row.close > row.sma5 else None


class Breakout(Strategy):
    key, name, horizon, max_days = "h10", "Hacimli kırılım", "10 gün", 10
    about = "20 günlük zirve, normalin 1,5 katı hacimle kırıldığında alım."

    def entry(self, t, row, prev, rank):
        if not ok(row.high20, row.vol_ratio, row.sma50, row.rsi14, row.atr14):
            return None
        if row.close > row.high20 and row.vol_ratio > 1.5 and row.close > row.sma50 and row.rsi14 < 75:
            return self._sig(t, row, row.close - 2 * row.atr14, row.close + 3 * row.atr14,
                             row.vol_ratio, f"20 günlük zirve {row.high20:.2f} kırıldı, hacim {row.vol_ratio:.1f} kat")
        return None


class Pullback(Strategy):
    key, name, horizon, max_days = "h20", "Trend içi geri çekilme", "20 gün", 20
    about = "Güçlü trendde fiyat 20 günlük ortalamaya geri çekilip yeniden yukarı döndüğünde alım."

    def entry(self, t, row, prev, rank):
        if not ok(row.sma20, row.sma50, row.sma100, row.macd_h, prev.macd_h, row.rsi14, row.atr14):
            return None
        trend = row.sma20 > row.sma50 > row.sma100
        touched = row.low <= row.sma20 * 1.01 and row.close > row.sma20
        turning = row.macd_h > prev.macd_h
        if trend and touched and turning and 40 <= row.rsi14 <= 62:
            return self._sig(t, row, row.close - 2.5 * row.atr14, row.close + 4 * row.atr14,
                             (row.sma20 / row.sma50 - 1) * 100,
                             "Yükseliş trendinde 20 günlük ortalamadan destek aldı")
        return None


class Momentum(Strategy):
    key, name, horizon, max_days = "h50", "Orta vade momentum", "50 gün", 50
    about = "Son 3 ayın en güçlü 5 hissesinden, trendi bozulmamış olanlar."

    def entry(self, t, row, prev, rank):
        r = rank.get("roc63")
        if not ok(r, row.roc63, row.sma50, row.sma100, row.rsi14, row.atr14):
            return None
        if r <= 5 and row.roc63 > 0 and row.close > row.sma50 > row.sma100 and row.rsi14 < 75:
            return self._sig(t, row, row.close - 3 * row.atr14, None, row.roc63,
                             f"3 aylık getiri %{row.roc63:.1f}, BIST 30'da {int(r)}. sırada")
        return None

    def exit_on_close(self, pos, row):
        return "Fiyat 50 günlük ortalamanın altına indi" if ok(row.sma50) and row.close < row.sma50 else None


class LongTrend(Strategy):
    key, name, horizon, max_days = "h100", "Uzun vade trend", "100 gün", 100
    about = "200 günlük ortalamanın üzerinde, son 6 ayın en güçlü 5 hissesi."

    def entry(self, t, row, prev, rank):
        r = rank.get("roc126")
        if not ok(r, row.roc126, row.sma50, row.sma200, row.atr14):
            return None
        if r <= 5 and row.roc126 > 0 and row.close > row.sma200 and row.sma50 > row.sma200:
            return self._sig(t, row, row.close - 4 * row.atr14, None, row.roc126,
                             f"6 aylık getiri %{row.roc126:.1f}, BIST 30'da {int(r)}. sırada")
        return None

    def exit_on_close(self, pos, row):
        return "Fiyat 100 günlük ortalamanın altına indi" if ok(row.sma100) and row.close < row.sma100 else None


STRATEGIES: list[Strategy] = [ShortBounce(), Breakout(), Pullback(), Momentum(), LongTrend()]
BY_KEY = {s.key: s for s in STRATEGIES}


def scan(frames: dict, ranks: dict, date: pd.Timestamp) -> dict[str, list[Signal]]:
    """Verilen günün kapanışına göre her strateji için sinyaller, en güçlüsü başta."""
    out: dict[str, list[Signal]] = {s.key: [] for s in STRATEGIES}
    for t, f in frames.items():
        if date not in f.index:
            continue
        i = f.index.get_loc(date)
        if i < 1:
            continue
        row, prev = f.iloc[i], f.iloc[i - 1]
        rank = {k: (r.at[date, t] if date in r.index and t in r.columns else None) for k, r in ranks.items()}
        for s in STRATEGIES:
            sig = s.entry(t, row, prev, rank)
            if sig and sig.stop < sig.price:
                out[s.key].append(sig)
    for k in out:
        out[k].sort(key=lambda x: x.score, reverse=True)
    return out
