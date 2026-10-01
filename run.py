"""System Bot komut satırı.

  python run.py monitor     seans içi kontrol (bekleyen alımlar, stop/hedef, sert hareketler)
  python run.py eod         gün sonu: çıkışlar, tarama, yarının emirleri, rapor
  python run.py backtest    kuralları son 3 yılın verisinde dener
  python run.py telegram    Telegram bağlantısını dener

Seçenekler: --demo (rastgele veriyle dene), --dry (mesaj gönderme, ekrana yaz)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import config
from systembot import data, engine, indicators, messages, report
from systembot.notify import claude_comment, news, send_telegram
from systembot.portfolio import Portfolio

STATE = "state/portfolio.json"
BT_FILE = "state/backtest.json"


def load_frames(demo: bool):
    tickers = config.TICKERS
    if demo:
        raw = data.synthetic_daily(tickers + [config.BENCHMARK])
    else:
        raw = data.load_daily(tickers + [config.BENCHMARK])
    bench = raw.pop(config.BENCHMARK, None)
    raw = {t: df for t, df in raw.items() if len(df) >= config.MIN_BARS}
    missing = sorted(set(tickers) - set(raw))
    if missing:
        print("Verisi alınamayan veya geçmişi kısa hisseler:", ", ".join(missing))
    if not raw:
        sys.exit("Hiç veri alınamadı.")
    frames, ranks = indicators.build(raw)
    return frames, ranks, bench


def today_str(frames=None, demo=False) -> str:
    if demo and frames:
        return str(max(f.index.max() for f in frames.values()).date())
    return str(data.now_tr().date())


def cmd_monitor(a):
    pf = Portfolio.load(a.state)
    need = sorted({p["ticker"] for p in pf.positions} | {o["ticker"] for o in pf.pending})
    if not need:
        print("Açık pozisyon veya bekleyen emir yok.")
        return
    if a.demo:
        frames, _, _ = load_frames(True)
        quotes = data.synthetic_intraday({t: frames[t] for t in need if t in frames})
        today = str(data.now_tr().date())
    else:
        quotes = data.load_intraday(need)
        today = str(data.now_tr().date())
    if not quotes:
        print("Bugün için gün içi veri yok (tatil ya da seans kapalı).")
        return
    events = engine.monitor(pf, quotes, today)
    pf.save(a.state)
    msg = messages.monitor_message(events)
    if msg:
        send_telegram(msg, a.dry)
    else:
        print("Bildirilecek olay yok.")
    report.write(pf, None, _load_bt(), a.docs)


def cmd_eod(a):
    pf = Portfolio.load(a.state)
    frames, ranks, bench = load_frames(a.demo)
    today = today_str(frames, a.demo)
    res = engine.end_of_day(pf, frames, ranks, today, bench)
    if res is None:
        print("Bugün işlem günü değil, veri gelmedi ya da gün sonu zaten çalıştı.")
        return
    pf.save(a.state)
    news_map = {} if a.demo else {s.ticker: news(s.ticker, config.NEWS_PER_TICKER) for s in res["queued"]}
    import datetime as dt
    weekly = messages.weekly_message(pf) if (a.weekly or dt.date.fromisoformat(today).weekday() == 4) else None
    summary_txt = messages.eod_message(pf, res, news_map, None, None)
    comment = None if a.demo else claude_comment(summary_txt)
    send_telegram(messages.eod_message(pf, res, news_map, comment, weekly), a.dry)
    report.write(pf, res, _load_bt(), a.docs)


def cmd_backtest(a):
    frames, ranks, bench = load_frames(a.demo)
    bt = engine.backtest(frames, ranks, bench)
    os.makedirs("state", exist_ok=True)
    with open(a.bt_file, "w", encoding="utf-8") as f:
        json.dump(bt, f, ensure_ascii=False, indent=1)
    prev = None
    try:
        with open("state/backtest_v1.json", encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        pass
    send_telegram(messages.backtest_message(bt, None if a.demo else prev), a.dry)
    report.write(Portfolio.load(a.state), None, bt, a.docs)


def cmd_telegram(a):
    ok = send_telegram("System Bot bağlandı. Bildirimler bu sohbete gelecek.", a.dry)
    print("Gönderildi." if ok else "Gönderilemedi: TELEGRAM_TOKEN ve TELEGRAM_CHAT_ID ayarlarını kontrol et.")


def _load_bt():
    try:
        with open(BT_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="System Bot BIST hayali portföy sistemi")
    ap.add_argument("mode", choices=["monitor", "eod", "backtest", "telegram"])
    ap.add_argument("--demo", action="store_true", help="rastgele veriyle dene")
    ap.add_argument("--dry", action="store_true", help="mesaj gönderme, ekrana yaz")
    ap.add_argument("--weekly", action="store_true", help="gün sonuna haftalık karneyi ekle")
    a = ap.parse_args()
    a.state = "state/demo.json" if a.demo else STATE
    a.bt_file = "state/demo_backtest.json" if a.demo else BT_FILE
    a.docs = "state/demo_docs" if a.demo else "docs"
    if a.demo:
        BT_FILE = a.bt_file
    {"monitor": cmd_monitor, "eod": cmd_eod, "backtest": cmd_backtest, "telegram": cmd_telegram}[a.mode](a)
