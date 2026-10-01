"""Geçmiş test ve canlı (gecikmeli) çalışma. İkisi aynı kuralları ve aynı portföy kodunu kullanır."""
from __future__ import annotations

import pandas as pd

import config
from .portfolio import Portfolio
from .strategies import STRATEGIES, scan


def market_regime(bench: pd.DataFrame | None) -> pd.Series | None:
    """Her gün için: BIST 30, kendi uzun ortalamasının üzerinde mi? (veri yoksa filtre uygulanmaz)"""
    if not config.MARKET_FILTER or bench is None or bench.empty:
        return None
    c = bench["close"]
    ma = c.rolling(config.MARKET_FILTER_MA).mean()
    return (c > ma) | ma.isna()


def market_ok(regime: pd.Series | None, d: pd.Timestamp) -> bool:
    if regime is None:
        return True
    r = regime.loc[:d]
    return bool(r.iloc[-1]) if len(r) else True


def _closes(frames: dict, d: pd.Timestamp) -> dict[str, float]:
    return {t: float(f.at[d, "close"]) for t, f in frames.items() if d in f.index}


# ====================================================================== geçmiş test

def backtest(frames: dict, ranks: dict, bench: pd.DataFrame | None = None, warmup: int = 130) -> dict:
    dates = sorted(set().union(*[f.index for f in frames.values()]))
    pf = Portfolio()
    regime = market_regime(bench)
    blocked_days = 0
    curve = []
    for i, d in enumerate(dates):
        if i < warmup:
            continue
        ds = str(d.date())
        prices = _closes(frames, d)
        # 1) dünkü sinyaller bugünün açılışında alınır
        for o in list(pf.pending):
            pf.pending.remove(o)
            f = frames[o["ticker"]]
            if d in f.index:
                pf.open(o, float(f.at[d, "open"]), ds, prices)
        # 2) gün içi stop/hedef, 3) kapanış kuralları
        for p in list(pf.positions):
            f = frames[p["ticker"]]
            if d not in f.index:
                continue
            r = f.loc[d]
            bar = {"open": r.open, "high": r.high, "low": r.low, "last": r.close}
            ex = pf.intraday_exit(p, bar, entered_today=False)
            if ex:
                pf.close(p, ex[0], ds, ex[1])
                continue
            p["days_held"] += 1
            why = pf.close_exit(p, r)
            if why:
                pf.close(p, float(r.close), ds, why)
        # 4) kapanışta tarama, ertesi gün için emir (piyasa filtresi izin veriyorsa)
        if not market_ok(regime, d):
            blocked_days += 1
            sigs_today = {}
        else:
            sigs_today = scan(frames, ranks, d)
        for key, sigs in sigs_today.items():
            for s in sigs:
                if pf.slots_free(key) <= 0:
                    break
                pf.queue(s, ds, prices)
        curve.append({"date": ds, "total": pf.equity(prices),
                      **{s.key: pf.sleeve_equity(s.key, prices) for s in STRATEGIES}})
    out = summarize(pf, curve, bench)
    if out:
        out["market_filter"] = regime is not None
        out["blocked_pct"] = round(blocked_days / max(len(curve), 1) * 100)
    return out


def _max_dd(values: list[float]) -> float:
    peak, dd = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        dd = min(dd, v / peak - 1)
    return dd * 100


def summarize(pf: Portfolio, curve: list[dict], bench: pd.DataFrame | None) -> dict:
    if not curve:
        return {}
    start, end = curve[0]["date"], curve[-1]["date"]
    per = pf.capital / len(STRATEGIES)
    rows = []
    for s in STRATEGIES:
        tr = [t for t in pf.closed if t["strategy"] == s.key]
        wins = [t for t in tr if t["pnl"] > 0]
        vals = [c[s.key] for c in curve]
        rows.append({
            "key": s.key, "name": s.name, "horizon": s.horizon,
            "return_pct": round((vals[-1] / per - 1) * 100, 1),
            "max_dd_pct": round(_max_dd(vals), 1),
            "trades": len(tr),
            "win_rate": round(len(wins) / len(tr) * 100, 0) if tr else None,
            "avg_trade_pct": round(sum(t["pnl_pct"] for t in tr) / len(tr), 2) if tr else None,
        })
    total = [c["total"] for c in curve]
    out = {"start": start, "end": end, "strategies": rows,
           "total_return_pct": round((total[-1] / pf.capital - 1) * 100, 1),
           "total_max_dd_pct": round(_max_dd(total), 1), "benchmark_pct": None}
    if bench is not None and not bench.empty:
        b = bench.loc[(bench.index >= pd.Timestamp(start)) & (bench.index <= pd.Timestamp(end)), "close"]
        if len(b) > 1:
            out["benchmark_pct"] = round((b.iloc[-1] / b.iloc[0] - 1) * 100, 1)
    return out


# ====================================================================== canlı

def monitor(pf: Portfolio, quotes: dict[str, dict], today: str) -> list[dict]:
    """Seans içinde: bekleyen emirleri aç, stop/hedefleri kontrol et, sert hareketleri bildir."""
    events = []
    prices = {t: q["last"] for t, q in quotes.items()}
    for o in list(pf.pending):
        if o["signal_date"] >= today:
            continue
        q = quotes.get(o["ticker"])
        if not q:
            continue
        pf.pending.remove(o)
        pos = pf.open(o, q["last"], today, prices)
        if pos:
            events.append({"type": "open", "pos": pos, "time": q["time"]})
        else:
            why = "fiyat stop seviyesinin altında açıldı" if q["last"] <= o["stop"] else "bütçe 1 lota yetmedi"
            events.append({"type": "skip", "order": o, "why": why, "time": q["time"]})
    for p in list(pf.positions):
        q = quotes.get(p["ticker"])
        if not q:
            continue
        ex = pf.intraday_exit(p, q, entered_today=p["entry_date"] == today)
        if ex:
            events.append({"type": "close", "trade": pf.close(p, ex[0], today, ex[1]), "time": q["time"]})
            continue
        if q.get("prev_close"):
            chg = (q["last"] / q["prev_close"] - 1) * 100
            tag = f"{p['ticker']}:{'+' if chg > 0 else '-'}"  # aynı hisse için günde bir uyarı
            if abs(chg) >= config.MOVE_ALERT_PCT and pf.alerts.get(tag) != today:
                pf.alerts[tag] = today
                events.append({"type": "move", "pos": p, "chg": chg, "last": q["last"], "time": q["time"]})
    return events


def end_of_day(pf: Portfolio, frames: dict, ranks: dict, today: str,
               bench: pd.DataFrame | None = None) -> dict | None:
    """Kapanıştan sonra: günlük çubukla son kontroller, süre/trend çıkışları, yarın için tarama."""
    d = pd.Timestamp(today)
    if not any(d in f.index for f in frames.values()):
        return None  # bugün işlem günü değil ya da veri gelmedi
    if pf.meta.get("last_eod") == today:
        return None  # bugün zaten çalıştı
    prices = _closes(frames, d)
    closed = []
    for o in list(pf.pending):  # gün içinde açılamayan eski emirler iptal
        if o["signal_date"] < today:
            pf.pending.remove(o)
    for p in list(pf.positions):
        f = frames.get(p["ticker"])
        if f is None or d not in f.index:
            continue
        r = f.loc[d]
        bar = {"open": r.open, "high": r.high, "low": r.low, "last": r.close}
        ex = pf.intraday_exit(p, bar, entered_today=p["entry_date"] == today)
        if ex:
            closed.append(pf.close(p, ex[0], today, ex[1]))
            continue
        p["days_held"] += 1
        why = pf.close_exit(p, r)
        if why:
            closed.append(pf.close(p, float(r.close), today, why))
    signals = scan(frames, ranks, d)
    market_up = market_ok(market_regime(bench), d)
    queued = []
    for key, sigs in (signals.items() if market_up else []):
        for s in sigs:
            if pf.slots_free(key) <= 0:
                break
            if pf.queue(s, today, prices):
                queued.append(s)
    bench_close = None
    if bench is not None and d in bench.index:
        bench_close = float(bench.at[d, "close"])
        pf.meta.setdefault("bench_start", {"date": today, "close": bench_close})
    pf.meta.setdefault("start_date", today)
    pf.meta["last_eod"] = today
    pf.alerts = {}
    snap = {"date": today, "total": round(pf.equity(prices), 2),
            **{s.key: round(pf.sleeve_equity(s.key, prices), 2) for s in STRATEGIES}}
    if bench_close:
        snap["bench"] = bench_close
    pf.history = [h for h in pf.history if h["date"] != today] + [snap]
    return {"closed": closed, "signals": signals, "queued": queued, "prices": prices, "snap": snap,
            "market_up": market_up}
