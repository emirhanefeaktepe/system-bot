"""Telegram mesaj metinleri (Türkçe)."""
from __future__ import annotations

import config
from .notify import esc
from .portfolio import Portfolio
from .strategies import BY_KEY, STRATEGIES


def tl(x: float | None, d: int = 2) -> str:
    if x is None:
        return "—"
    s = f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def pct(x: float | None, d: int = 1) -> str:
    return "—" if x is None else ("+" if x >= 0 else "") + tl(x, d) + "%"


def _h(key: str) -> str:
    s = BY_KEY[key]
    return f"{s.horizon} · {s.name}"


def monitor_message(events: list[dict]) -> str | None:
    if not events:
        return None
    out = ["<b>System Bot · seans içi</b>"]
    for e in events:
        if e["type"] == "open":
            p = e["pos"]
            tgt = f" · Hedef {tl(p['target'])}" if p["target"] else ""
            out.append(f"\n🟢 <b>SANAL ALIM {esc(p['ticker'])}</b> ({_h(p['strategy'])})\n"
                       f"{p['lots']} lot × {tl(p['entry_price'])} = {tl(p['cost'])} TL\n"
                       f"Stop {tl(p['stop'])}{tgt}\n<i>{esc(p['reason'])}</i>")
        elif e["type"] == "close":
            t = e["trade"]
            mark = "✅" if t["pnl"] > 0 else "🔻"
            out.append(f"\n{mark} <b>SANAL SATIŞ {esc(t['ticker'])}</b> ({_h(t['strategy'])})\n"
                       f"{tl(t['entry_price'])} → {tl(t['exit_price'])} · {pct(t['pnl_pct'], 2)} "
                       f"({'+' if t['pnl'] >= 0 else ''}{tl(t['pnl'])} TL)\nNeden: {esc(t['exit_reason'])}")
        elif e["type"] == "move":
            p = e["pos"]
            out.append(f"\n⚠️ <b>{esc(p['ticker'])}</b> bugün {pct(e['chg'])} ({tl(e['last'])}). "
                       f"Elde var: {_h(p['strategy'])}, stop {tl(p['stop'])}.")
        elif e["type"] == "skip":
            o = e["order"]
            out.append(f"\n⏭ {esc(o['ticker'])} alımı yapılmadı: {esc(e['why'])}.")
    out.append(f"\n<i>Veriler ~15 dk gecikmeli · saat {events[-1].get('time', '')}</i>")
    return "\n".join(out)


def eod_message(pf: Portfolio, res: dict, news_map: dict, comment: str | None, weekly: str | None) -> str:
    snap, prices = res["snap"], res["prices"]
    total = snap["total"]
    out = [f"<b>System Bot · gün sonu {snap['date']}</b>",
           f"Hayali portföy: <b>{tl(total)} TL</b> ({pct((total / pf.capital - 1) * 100, 2)} başlangıçtan)"]
    bs = pf.meta.get("bench_start")
    if bs and snap.get("bench"):
        out.append(f"BIST 30 aynı sürede: {pct((snap['bench'] / bs['close'] - 1) * 100, 2)}")
    per = pf.capital / len(STRATEGIES)
    out.append("")
    for s in STRATEGIES:
        v = snap[s.key]
        n = len(pf.sleeve_positions(s.key))
        out.append(f"{s.horizon}: {tl(v)} TL ({pct((v / per - 1) * 100)}) · {n} açık pozisyon")

    if res["closed"]:
        out.append("\n<b>Bugün kapananlar</b>")
        for t in res["closed"]:
            out.append(f"{'✅' if t['pnl'] > 0 else '🔻'} {esc(t['ticker'])} ({BY_KEY[t['strategy']].horizon}) "
                       f"{pct(t['pnl_pct'], 2)} · {esc(t['exit_reason'])}")

    if pf.positions:
        out.append("\n<b>Açık pozisyonlar</b>")
        for p in sorted(pf.positions, key=lambda p: p["strategy"]):
            last = prices.get(p["ticker"], p["entry_price"])
            ch = (last / p["entry_price"] - 1) * 100
            tgt = f", hedef {tl(p['target'])}" if p["target"] else ""
            out.append(f"• {esc(p['ticker'])} ({BY_KEY[p['strategy']].horizon}) {tl(last)} · {pct(ch)} · "
                       f"stop {tl(p['stop'])}{tgt} · {p['days_held']}/{p['max_days']} gün")

    if res["queued"]:
        out.append("\n<b>Yarın açılışta sanal alım</b>")
        for s in res["queued"]:
            tgt = f" · hedef {tl(s.target)}" if s.target else ""
            out.append(f"• <b>{esc(s.ticker)}</b> ({BY_KEY[s.strategy].horizon}) ~{tl(s.price)} · stop {tl(s.stop)}{tgt}\n"
                       f"  <i>{esc(s.reason)}</i>")
            for n in news_map.get(s.ticker, []):
                out.append(f"  📰 {esc(n['title'])}")

    out.append("\n<b>Vadelere göre fırsat listesi</b>")
    for s in STRATEGIES:
        sigs = res["signals"].get(s.key, [])[:config.CANDIDATES_PER_STRATEGY]
        if not sigs:
            out.append(f"{s.horizon}: kurala uyan hisse yok.")
            continue
        items = []
        for g in sigs:
            risk = (g.price - g.stop) / g.price * 100
            items.append(f"{esc(g.ticker)} {tl(g.price)} (stop −%{tl(risk, 1)})")
        out.append(f"{s.horizon}: " + ", ".join(items))

    if comment:
        out.append("\n<b>Claude yorumu</b>\n" + esc(comment))
    if weekly:
        out.append("\n" + weekly)
    out.append("\n<i>Kural tabanlı sanal işlemler, yatırım tavsiyesi değildir.</i>")
    return "\n".join(out)


def weekly_message(pf: Portfolio) -> str:
    out = ["<b>Haftalık karne (başlangıçtan bu yana)</b>"]
    per = pf.capital / len(STRATEGIES)
    last = pf.history[-1] if pf.history else {}
    for s in STRATEGIES:
        tr = [t for t in pf.closed if t["strategy"] == s.key]
        wins = sum(1 for t in tr if t["pnl"] > 0)
        wr = f"%{round(wins / len(tr) * 100)}" if tr else "—"
        v = last.get(s.key, per)
        out.append(f"{s.horizon}: {pct((v / per - 1) * 100)} · {len(tr)} işlem · kazanma oranı {wr}")
    if len(pf.closed) < 20:
        out.append("<i>Henüz 20'den az işlem var; sonuçlar istatistiksel olarak anlamlı değil.</i>")
    return "\n".join(out)


def backtest_message(bt: dict) -> str:
    out = [f"<b>Geçmiş test {bt['start']} → {bt['end']}</b>",
           f"Toplam: {pct(bt['total_return_pct'])} · en büyük düşüş {pct(bt['total_max_dd_pct'])}"]
    if bt.get("benchmark_pct") is not None:
        out.append(f"BIST 30 aynı sürede: {pct(bt['benchmark_pct'])}")
    out.append("")
    for r in bt["strategies"]:
        wr = f"%{r['win_rate']:.0f}" if r["win_rate"] is not None else "—"
        out.append(f"{r['horizon']} ({r['name']}): {pct(r['return_pct'])}, düşüş {pct(r['max_dd_pct'])}, "
                   f"{r['trades']} işlem, kazanma {wr}, ort. {pct(r['avg_trade_pct'], 2)}")
    out.append("\n<i>Geçmiş performans geleceği garanti etmez. Komisyon 0, kayma %0,1 varsayıldı.</i>")
    return "\n".join(out)
