#!/usr/bin/env python3
"""
Live Signal Monitor - KEYLESS paper trading on REAL exchange candles.

- Fetches live klines from Binance USDT-M PUBLIC API (no API keys needed)
- Runs the bot's ACTUAL RSI2MeanReversionStrategy module
- Tracks virtual positions: entry, SL (3% price), RSI-exit, fees 0.05%/side
- Logs everything to a log file + trades JSON

Usage:
  python3 tools/live_signal_monitor.py --tf 4h --coins BTCUSDT,ETHUSDT --interval 60
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import requests

# Make the bot's strategy module importable (same code that trades live)
_HERE = os.path.dirname(os.path.abspath(__file__))
_BOT_ENGINE = os.path.join(_HERE, "..", "bot-engine")
sys.path.insert(0, _BOT_ENGINE)

from bot.strategy import RSI2MeanReversionStrategy, Signal  # noqa: E402

FAPI = "https://fapi.binance.com/fapi/v1/klines"
FEE_PCT = 0.05          # taker fee % per side
SL_PCT = 3.0            # price-based stop loss %
LEV = 10                # leverage for ROE display
MARGIN = 100.0          # virtual USDT margin per trade

log = logging.getLogger("monitor")


def fetch_klines(symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
    r = requests.get(FAPI, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=15)
    r.raise_for_status()
    rows = r.json()
    cols = ["open_time", "open", "high", "low", "close", "volume",
            "close_time", "qv", "trades", "tbb", "tbq", "ig"]
    df = pd.DataFrame(rows, columns=cols)
    df["open_time"] = pd.to_datetime(df["open_time"].astype("int64"), unit="ms", utc=True)
    df = df.set_index("open_time")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    return df[["open", "high", "low", "close", "volume"]]


class VirtualBook:
    """Virtual position tracker with fee-aware PnL."""

    def __init__(self, trades_file: str):
        self.pos = None  # dict(side, entry, qty, notional, opened_at)
        self.trades_file = trades_file
        self.realized_roe = 0.0
        self.wins = 0
        self.losses = 0
        self._load()

    def _load(self):
        try:
            with open(self.trades_file) as f:
                d = json.load(f)
            self.realized_roe = d.get("realized_roe", 0.0)
            self.wins = d.get("wins", 0)
            self.losses = d.get("losses", 0)
            if d.get("open_pos"):
                self.pos = d["open_pos"]
        except Exception:
            pass

    def save(self):
        try:
            with open(self.trades_file, "w") as f:
                json.dump({
                    "realized_roe": self.realized_roe,
                    "wins": self.wins,
                    "losses": self.losses,
                    "open_pos": self.pos,
                    "updated": datetime.now(timezone.utc).isoformat(),
                }, f, indent=1)
        except Exception as e:
            log.warning("save failed: %s", e)

    def open(self, side: str, price: float, ts):
        qty = (MARGIN * LEV) / price
        self.pos = {"side": side, "entry": price, "qty": qty,
                    "notional": MARGIN * LEV, "opened_at": str(ts)}
        pnl_fees = self.pos["notional"] * FEE_PCT / 100.0  # entry fee
        self.pos["fees_paid"] = pnl_fees
        log.info("OPEN  %s @ %.6g | margin=%.0f notional=%.0f (fee %.3f)",
                 side, price, MARGIN, self.pos["notional"], pnl_fees)

    def close(self, price: float, ts, reason: str):
        p = self.pos
        if p is None:
            return
        if p["side"] == "LONG":
            price_pnl = (price - p["entry"]) / p["entry"] * p["notional"]
        else:
            price_pnl = (p["entry"] - price) / p["entry"] * p["notional"]
        exit_fee = p["notional"] * FEE_PCT / 100.0
        net = price_pnl - p.get("fees_paid", 0.0) - exit_fee
        roe = net / MARGIN * 100.0
        self.realized_roe += roe
        if roe >= 0:
            self.wins += 1
        else:
            self.losses += 1
        n = self.wins + self.losses
        wr = self.wins / n * 100 if n else 0.0
        log.info("CLOSE %s @ %.6g | %s | net PnL $%.2f (%+.2f%% ROE) | "
                 "closed trades=%d WR=%.1f%% cumulative=%+.2f%% ROE",
                 p["side"], price, reason, net, roe, n, wr, self.realized_roe)
        self.pos = None


def run(tf: str, coins: list, poll_s: int, log_file: str, trades_file: str):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file)],
        force=True,
    )
    log.info("=== RSI-2 LIVE SIGNAL MONITOR | tf=%s coins=%s poll=%ss ===", tf, coins, poll_s)
    log.info("Virtual config: margin=%.0f USDT lev=%dx SL=%.1f%% price fee=%.2f%%/side", MARGIN, LEV, SL_PCT, FEE_PCT)

    state = {}
    for s in coins:
        strat = RSI2MeanReversionStrategy()
        seeded = False
        state[s] = {"strat": strat, "seeded": seeded}

    book = VirtualBook(trades_file)
    stop = False

    def _sigint(_a, _b):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGINT, _sigint)
    signal.signal(signal.SIGTERM, _sigint)

    tick = 0
    while not stop:
        for s in coins:
            st = state[s]
            try:
                df = fetch_klines(s, tf, 300)
            except Exception as e:
                log.warning("%s fetch failed: %s", s, e)
                continue

            # Drop the still-forming candle? NO - bot trades on closed candles data
            # but for signal timing we use the same df as engine sees (includes live candle).
            try:
                res = st["strat"].analyze(df)
            except Exception as e:
                log.warning("%s analyze failed: %s", s, e)
                continue
            if res is None:
                continue

            last = df.iloc[-1]
            close, high, low = float(last["close"]), float(last["high"]), float(last["low"])
            ts = df.index[-1]

            # Seed: first tick only learns state (matches bot strict-mode: no instant entry)
            if not st["seeded"]:
                st["seeded"] = True
                st["strat"].reset_cross_state()
                log.info("%s seeded | close=%.6g rsi2=%.1f sma200=%.6g signal=%s",
                         s, close, res.rsi_2, res.sma_200, res.signal.value)
                continue

            # --- Manage open virtual position first (SL via live candle extremes) ---
            if book.pos is not None:
                p = book.pos
                if p["side"] == "LONG":
                    if low <= p["entry"] * (1 - SL_PCT / 100.0):
                        book.close(p["entry"] * (1 - SL_PCT / 100.0), ts, "SL HIT (-3% price)")
                    elif res.exit_long:
                        book.close(close, ts, "RSI-EXIT (rsi2=%.0f > threshold)" % res.rsi_2)
                else:  # SHORT
                    if high >= p["entry"] * (1 + SL_PCT / 100.0):
                        book.close(p["entry"] * (1 + SL_PCT / 100.0), ts, "SL HIT (+3% price)")
                    elif res.exit_short:
                        book.close(close, ts, "RSI-EXIT (rsi2=%.0f < threshold)" % res.rsi_2)
                book.save()

            # --- Entry on FRESH signal (bot semantics: just_crossed) ---
            if book.pos is None and res.just_crossed:
                if res.signal == Signal.BUY:
                    book.open("LONG", close, ts)
                elif res.signal == Signal.SELL:
                    book.open("SHORT", close, ts)
                book.save()

        tick += 1
        if tick % 30 == 0:  # heartbeat every ~30 polls
            p = book.pos
            n = book.wins + book.losses
            wr = book.wins / n * 100 if n else 0.0
            log.info("heartbeat | ticks=%d | open_pos=%s | closed=%d WR=%.1f%% cum=%+.2f%% ROE",
                     tick,
                     ("%-4s @ %.6g" % (p["side"], p["entry"])) if p else "none",
                     n, wr, book.realized_roe)
        time.sleep(poll_s)

    log.info("monitor stopped")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="4h")
    ap.add_argument("--coins", default="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,DOGEUSDT")
    ap.add_argument("--interval", type=int, default=60, help="poll seconds")
    ap.add_argument("--tag", default="4h", help="suffix for log/trade files")
    a = ap.parse_args()

    base = "/home/z/my-project/logs"
    os.makedirs(base, exist_ok=True)
    run(
        tf=a.tf,
        coins=[c.strip().upper() for c in a.coins.split(",") if c.strip()],
        poll_s=a.interval,
        log_file=os.path.join(base, f"live_monitor_{a.tag}.log"),
        trades_file=os.path.join(base, f"live_trades_{a.tag}.json"),
    )


if __name__ == "__main__":
    main()
