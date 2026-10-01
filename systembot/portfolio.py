"""Hayali portföy: her strateji kendi bölmesinde (sleeve) para tutar."""
from __future__ import annotations

import json
import math
import os
import uuid

import config
from .strategies import BY_KEY, STRATEGIES, Signal


class Portfolio:
    def __init__(self, capital: float = config.CAPITAL):
        per = capital / len(STRATEGIES)
        self.capital = capital
        self.cash = {s.key: per for s in STRATEGIES}
        self.positions: list[dict] = []
        self.pending: list[dict] = []
        self.closed: list[dict] = []
        self.history: list[dict] = []     # gün sonu değer kaydı
        self.alerts: dict[str, str] = {}  # gün içi hareket uyarıları (tekrarı önlemek için)
        self.meta: dict = {}

    # ---------------------------------------------------------------- kayıt
    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in
                ("capital", "cash", "positions", "pending", "closed", "history", "alerts", "meta")}

    @classmethod
    def from_dict(cls, d: dict) -> "Portfolio":
        p = cls(d.get("capital", config.CAPITAL))
        for k in ("cash", "positions", "pending", "closed", "history", "alerts", "meta"):
            if k in d:
                setattr(p, k, d[k])
        for s in STRATEGIES:  # sonradan eklenen strateji için bölme aç
            p.cash.setdefault(s.key, p.capital / len(STRATEGIES))
        return p

    @classmethod
    def load(cls, path: str) -> "Portfolio":
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        return cls()

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    # ---------------------------------------------------------------- değer
    def sleeve_positions(self, key: str) -> list[dict]:
        return [p for p in self.positions if p["strategy"] == key]

    def sleeve_equity(self, key: str, prices: dict[str, float]) -> float:
        return self.cash[key] + sum(p["lots"] * prices.get(p["ticker"], p["entry_price"])
                                    for p in self.sleeve_positions(key))

    def equity(self, prices: dict[str, float]) -> float:
        return sum(self.sleeve_equity(s.key, prices) for s in STRATEGIES)

    def slots_free(self, key: str) -> int:
        used = len(self.sleeve_positions(key)) + sum(1 for o in self.pending if o["strategy"] == key)
        return config.MAX_POS_PER_SLEEVE - used

    def holds(self, key: str, ticker: str) -> bool:
        return any(p["ticker"] == ticker for p in self.sleeve_positions(key)) or \
            any(o["ticker"] == ticker and o["strategy"] == key for o in self.pending)

    # ---------------------------------------------------------------- emirler
    def queue(self, sig: Signal, date: str, prices: dict[str, float] | None = None) -> bool:
        if self.slots_free(sig.strategy) <= 0 or self.holds(sig.strategy, sig.ticker):
            return False
        if self.lots_for(sig.strategy, sig.price, sig.stop, prices or {}) < 1:
            return False  # bu bölmenin bütçesi 1 lota yetmiyor; sıradaki adaya geç
        o = sig.to_dict()
        o["signal_date"] = date
        self.pending.append(o)
        return True

    def lots_for(self, key: str, price: float, stop: float, prices: dict[str, float]) -> int:
        fill = price * (1 + config.SLIPPAGE)
        eq = self.sleeve_equity(key, prices)
        budget = min(eq * config.MAX_POS_FRACTION, self.cash[key])
        risk_per_lot = max(fill - stop, fill * 0.005)
        budget = min(budget, eq * config.RISK_PER_TRADE / risk_per_lot * fill)
        return math.floor(budget / (fill * (1 + config.COMMISSION_RATE)))

    def open(self, order: dict, price: float, date: str, prices: dict[str, float]) -> dict | None:
        key = order["strategy"]
        if price <= order["stop"]:
            return None  # açılışta zaten stop seviyesinin altında: işlem açma
        fill = price * (1 + config.SLIPPAGE)
        lots = self.lots_for(key, price, order["stop"], prices)
        if lots < 1:
            return None
        cost = lots * fill * (1 + config.COMMISSION_RATE)
        self.cash[key] -= cost
        # stop ve hedefi gerçekleşen fiyata göre kaydır (aynı mesafeyi koru)
        shift = fill - order["price"]
        pos = {
            "id": uuid.uuid4().hex[:8], "ticker": order["ticker"], "strategy": key,
            "entry_date": date, "entry_price": round(fill, 4), "lots": lots, "cost": round(cost, 2),
            "stop": round(order["stop"] + shift, 2),
            "target": None if order["target"] is None else round(order["target"] + shift, 2),
            "max_days": order["max_days"], "days_held": 0, "reason": order["reason"],
        }
        self.positions.append(pos)
        return pos

    def close(self, pos: dict, price: float, date: str, why: str) -> dict:
        fill = price * (1 - config.SLIPPAGE)
        proceeds = pos["lots"] * fill * (1 - config.COMMISSION_RATE)
        self.cash[pos["strategy"]] += proceeds
        self.positions = [p for p in self.positions if p["id"] != pos["id"]]
        trade = {**pos, "exit_date": date, "exit_price": round(fill, 4), "exit_reason": why,
                 "pnl": round(proceeds - pos["cost"], 2),
                 "pnl_pct": round((proceeds / pos["cost"] - 1) * 100, 2)}
        self.closed.append(trade)
        return trade

    # ---------------------------------------------------------------- kurallar
    def intraday_exit(self, pos: dict, bar: dict, entered_today: bool) -> tuple[float, str] | None:
        """Stop veya hedef gün içinde tetiklendi mi? bar: open/high/low/last(close)."""
        low = bar["last"] if entered_today else bar["low"]
        high = bar["last"] if entered_today else bar["high"]
        if low <= pos["stop"]:
            px = pos["stop"] if entered_today else min(bar["open"], pos["stop"])
            return px, "Zarar durdur (stop)"
        if pos["target"] is not None and high >= pos["target"]:
            px = pos["target"] if entered_today else max(bar["open"], pos["target"])
            return px, "Hedef fiyat"
        return None

    def close_exit(self, pos: dict, row) -> str | None:
        why = BY_KEY[pos["strategy"]].exit_on_close(pos, row)
        if why:
            return why
        if pos["days_held"] >= pos["max_days"]:
            return f"Süre doldu ({pos['max_days']} gün)"
        return None
