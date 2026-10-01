"""Telegram bildirimleri, haber başlıkları ve isteğe bağlı Claude yorumu."""
from __future__ import annotations

import html
import os
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import requests


def send_telegram(text: str, dry: bool = False) -> bool:
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if dry or not token or not chat:
        print("----- Telegram mesajı (gönderilmedi) -----\n" + text + "\n")
        return False
    ok = True
    for part in _chunks(text, 3900):
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": part, "parse_mode": "HTML",
                                "disable_web_page_preview": "true"}, timeout=20)
        if r.status_code != 200:
            print("Telegram hatası:", r.status_code, r.text[:300])
            ok = False
    return ok


def _chunks(text: str, n: int):
    buf = ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > n and buf:
            yield buf
            buf = ""
        buf += line + "\n"
    if buf.strip():
        yield buf


def news(ticker: str, n: int = 2) -> list[dict]:
    """Google Haberler'den son başlıklar. Hata olursa boş liste döner."""
    url = f"https://news.google.com/rss/search?q={quote_plus(ticker + ' hisse')}+when:7d&hl=tr&gl=TR&ceid=TR:tr"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 system-bot"})
        root = ET.fromstring(r.content)
        out = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if title:
                out.append({"title": title, "link": link})
            if len(out) >= n:
                break
        return out
    except Exception as e:  # haber olmadan da rapor gider
        print("Haber alınamadı:", ticker, e)
        return []


def claude_comment(summary: str) -> str | None:
    """ANTHROPIC_API_KEY tanımlıysa gün sonu özetine kısa bir yorum ekler. Tanımlı değilse atlanır."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    prompt = ("Aşağıda Borsa İstanbul'da hayali parayla çalışan kural tabanlı bir sistemin gün sonu özeti var. "
              "Türkçe, en fazla 6 cümleyle yorumla: öne çıkan riskler, dikkat edilmesi gereken hisseler, "
              "stratejiler arasındaki farklar. Al/sat talimatı verme, kesin tahmin yapma.\n\n" + summary)
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=90, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": 700, "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", [])).strip() or None
    except Exception as e:
        print("Claude yorumu alınamadı:", e)
        return None


def esc(s) -> str:
    return html.escape(str(s), quote=False)
