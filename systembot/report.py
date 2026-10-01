"""GitHub Pages için durum sayfası (docs/index.html). Telefondan da okunur."""
from __future__ import annotations

import html
import json
import os

from .messages import pct, tl
from .portfolio import Portfolio
from .strategies import BY_KEY, STRATEGIES

CSS = """
:root{--bg:#eef2f6;--card:#fff;--ink:#13202d;--muted:#5a6878;--line:#d9e0e8;--accent:#1d4ed8;--up:#0d8a5c;--down:#c4362b}
@media (prefers-color-scheme:dark){:root{--bg:#0c1117;--card:#141b24;--ink:#e5ebf2;--muted:#93a1b1;--line:#243040;--accent:#7097ff;--up:#33c58f;--down:#ff6f62}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1000px;margin:0 auto;padding:20px 16px 40px;display:grid;gap:16px}
h1{margin:0;font-size:1.5rem}h2{margin:0 0 8px;font-size:1.05rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;min-width:0}
.muted{color:var(--muted)}.up{color:var(--up)}.down{color:var(--down)}
.big{font-size:1.8rem;font-variant-numeric:tabular-nums;font-weight:600}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:.9rem}
th,td{text-align:left;padding:7px 8px;border-top:1px solid var(--line);white-space:nowrap}th{color:var(--muted);font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;border-top:0}
svg{width:100%;height:auto;display:block}
"""


def _c(x: float | None) -> str:
    return "" if x is None else ("up" if x > 0 else "down" if x < 0 else "")


def _table(head: list[str], rows: list[list[str]], empty: str) -> str:
    if not rows:
        return f'<p class="muted">{empty}</p>'
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def _spark(hist: list[dict], capital: float) -> str:
    if len(hist) < 2:
        return '<p class="muted">Grafik birkaç işlem günü sonra oluşacak.</p>'
    w, h, pad = 640, 160, 24
    vals = [x["total"] for x in hist] + [capital]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    xs = lambda i: pad + i * (w - 2 * pad) / (len(hist) - 1)
    ys = lambda v: h - pad - (v - lo) / span * (h - 2 * pad)
    pts = " ".join(f"{xs(i):.1f},{ys(x['total']):.1f}" for i, x in enumerate(hist))
    base = ys(capital)
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Portföy değeri">'
            f'<line x1="{pad}" x2="{w - pad}" y1="{base:.1f}" y2="{base:.1f}" stroke="var(--line)" stroke-dasharray="4 4"/>'
            f'<polyline points="{pts}" fill="none" stroke="var(--accent)" stroke-width="2.5"/>'
            f'<text x="{pad}" y="{h - 4}" fill="var(--muted)" font-size="11">{hist[0]["date"]}</text>'
            f'<text x="{w - pad}" y="{h - 4}" fill="var(--muted)" font-size="11" text-anchor="end">{hist[-1]["date"]}</text>'
            f'<text x="{w - pad}" y="{base - 6:.1f}" fill="var(--muted)" font-size="11" text-anchor="end">başlangıç {tl(capital, 0)} TL</text>'
            "</svg>")


def write(pf: Portfolio, res: dict | None, bt: dict | None, out_dir: str = "docs") -> None:
    os.makedirs(out_dir, exist_ok=True)
    e = html.escape
    last = pf.history[-1] if pf.history else {"date": "—", "total": pf.capital}
    prices = (res or {}).get("prices", {})
    per = pf.capital / len(STRATEGIES)

    strat_rows = []
    for s in STRATEGIES:
        v = last.get(s.key, per)
        tr = [t for t in pf.closed if t["strategy"] == s.key]
        wins = sum(1 for t in tr if t["pnl"] > 0)
        r = (v / per - 1) * 100
        strat_rows.append([e(s.horizon), e(s.name), f"{tl(v)} TL", f'<span class="{_c(r)}">{pct(r)}</span>',
                           str(len(pf.sleeve_positions(s.key))), str(len(tr)),
                           f"%{round(wins / len(tr) * 100)}" if tr else "—"])

    pos_rows = []
    for p in pf.positions:
        lp = prices.get(p["ticker"], p["entry_price"])
        r = (lp / p["entry_price"] - 1) * 100
        pos_rows.append([f"<b>{e(p['ticker'])}</b>", e(BY_KEY[p['strategy']].horizon), p["entry_date"],
                         str(p["lots"]), tl(p["entry_price"]), tl(lp), f'<span class="{_c(r)}">{pct(r)}</span>',
                         tl(p["stop"]), tl(p["target"]), f"{p['days_held']}/{p['max_days']}"])

    pend_rows = [[f"<b>{e(o['ticker'])}</b>", e(BY_KEY[o['strategy']].horizon), tl(o["price"]), tl(o["stop"]),
                  tl(o["target"]), e(o["reason"])] for o in pf.pending]

    cand_rows = []
    for s in STRATEGIES:
        for g in ((res or {}).get("signals", {}).get(s.key, []))[:5]:
            cand_rows.append([e(s.horizon), f"<b>{e(g.ticker)}</b>", tl(g.price), tl(g.stop), tl(g.target), e(g.reason)])

    closed_rows = []
    for t in reversed(pf.closed[-30:]):
        closed_rows.append([f"<b>{e(t['ticker'])}</b>", e(BY_KEY[t['strategy']].horizon), t["entry_date"], t["exit_date"],
                            tl(t["entry_price"]), tl(t["exit_price"]),
                            f'<span class="{_c(t["pnl_pct"])}">{pct(t["pnl_pct"], 2)}</span>', e(t["exit_reason"])])

    bt_html = '<p class="muted">Geçmiş test henüz çalıştırılmadı.</p>'
    if bt:
        rows = [[e(r["horizon"]), e(r["name"]), f'<span class="{_c(r["return_pct"])}">{pct(r["return_pct"])}</span>',
                 pct(r["max_dd_pct"]), str(r["trades"]), f"%{r['win_rate']:.0f}" if r["win_rate"] is not None else "—",
                 pct(r["avg_trade_pct"], 2)] for r in bt["strategies"]]
        bench = f" · BIST 30: {pct(bt['benchmark_pct'])}" if bt.get("benchmark_pct") is not None else ""
        bt_html = (f'<p class="muted">{bt["start"]} → {bt["end"]} · toplam {pct(bt["total_return_pct"])}{bench}</p>'
                   + _table(["Vade", "Strateji", "Getiri", "En büyük düşüş", "İşlem", "Kazanma", "Ort. işlem"], rows, ""))

    total_r = (last["total"] / pf.capital - 1) * 100
    doc = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>System Bot Portföy</title><style>{CSS}</style></head>
<body><main>
<header><h1>System Bot · hayali BIST portföyü</h1><p class="muted">Son güncelleme: {e(str(last['date']))} · veriler ~15 dk gecikmeli · yatırım tavsiyesi değildir</p></header>
<section class="card"><div class="muted">Toplam değer</div><div class="big">{tl(last['total'])} TL <span class="{_c(total_r)}" style="font-size:1rem">{pct(total_r, 2)}</span></div>{_spark(pf.history, pf.capital)}</section>
<section class="card"><h2>Vadeler</h2>{_table(["Vade", "Strateji", "Değer", "Getiri", "Açık", "Kapanan", "Kazanma"], strat_rows, "")}</section>
<section class="card"><h2>Açık pozisyonlar</h2>{_table(["Hisse", "Vade", "Giriş tarihi", "Lot", "Giriş", "Son", "K/Z", "Stop", "Hedef", "Gün"], pos_rows, "Açık pozisyon yok.")}</section>
<section class="card"><h2>Sonraki seansta alınacaklar</h2>{_table(["Hisse", "Vade", "Fiyat", "Stop", "Hedef", "Neden"], pend_rows, "Bekleyen emir yok.")}</section>
<section class="card"><h2>Bugünkü fırsat listesi</h2>{_table(["Vade", "Hisse", "Fiyat", "Stop", "Hedef", "Neden"], cand_rows, "Bugün kurala uyan hisse yok.")}</section>
<section class="card"><h2>Kapanan işlemler</h2>{_table(["Hisse", "Vade", "Giriş", "Çıkış", "Alış", "Satış", "Sonuç", "Neden"], closed_rows, "Henüz kapanan işlem yok.")}</section>
<section class="card"><h2>Geçmiş test</h2>{bt_html}</section>
</main></body></html>"""
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(doc)
