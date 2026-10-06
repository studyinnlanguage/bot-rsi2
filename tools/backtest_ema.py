"""
EMA Quad (8/13/21/55) Backtest — REAL historical candles + fees
================================================================
Replicates the ORIGINAL bot's EMA mode EXACTLY as it traded:
- Entry : fresh EMA55 cross (EMA55 bottom -> LONG, EMA55 top -> SHORT) at candle close
- SL    : price-based (original default stop_loss_pct = 2%)
- TP    : fixed % (original default take_profit_pct = 6%, 1:3 RR)
          OR EMA55-flip close (original TP mode "BOTH"), reverse on flip
- Reset : after SL/TP close the bot calls reset_cross_state() -> it must wait
          for EMA55 to leave the extreme position (HOLD) before a new entry
- LIQ   : isolated-margin liquidation model (100/lev - maintenance margin)
          so high-leverage configurations are simulated honestly

Usage:
  python tools/backtest_ema.py --symbol BTCUSDT --tf 4h --years 3 --levs 10
  python tools/backtest_ema.py --symbol BTCUSDT --tf 5m --bars 25920 --levs 10,50,125
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot-engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest_rsi2 import fetch_klines  # noqa: E402  (same data loader as RSI-2 tool)
from bot.indicators import calculate_ema  # noqa: E402  (bot's real indicator code)


def precompute(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for p in (8, 13, 21, 55):
        out[f"ema_{p}"] = calculate_ema(out["close"], p)
    return out


def simulate(df: pd.DataFrame, sl_pct: float, tp_pct: float, fee_pct: float,
             lev: int, tp_mode: str = "both", mm_pct: float = 0.4) -> list:
    """Run the original EMA-mode trade simulation at one leverage."""
    # liquidation: margin wiped when adverse move ~ 100/lev % minus maintenance
    liq_move = max(0.05, 100.0 / lev - mm_pct) if lev > 1 else 10**9
    e8 = df["ema_8"].values; e13 = df["ema_13"].values
    e21 = df["ema_21"].values; e55 = df["ema_55"].values
    close = df["close"].values; high = df["high"].values; low = df["low"].values
    idx = df.index
    n = len(df)

    pos = None
    prev_sig = "HOLD"
    require_hold = False
    trades = []

    def signal_at(i):
        a, b, c, d = e8[i], e13[i], e21[i], e55[i]
        if np.isnan(a) or np.isnan(b) or np.isnan(c) or np.isnan(d):
            return "HOLD"
        if d < a and d < b and d < c:
            return "BUY"
        if d > a and d > b and d > c:
            return "SELL"
        return "HOLD"

    def close_trade(i, exit_price, reason):
        direction = 1 if pos["side"] == "LONG" else -1
        gross = (exit_price - pos["entry"]) / pos["entry"] * 100 * direction
        net = gross - fee_pct * 2  # entry + exit taker fees
        trades.append({"time": idx[i], "side": pos["side"], "entry": pos["entry"],
                       "exit": exit_price, "net": net, "roe": net * lev,
                       "reason": reason})

    for i in range(n):
        sig = signal_at(i)

        # ---------- manage open position ----------
        if pos is not None:
            hi, lo, px = high[i], low[i], close[i]
            exit_price = reason = None
            if pos["side"] == "LONG":
                liq_price = pos["entry"] * (1 - liq_move / 100)
                if lo <= liq_price:
                    exit_price, reason = liq_price, "LIQUIDATED"
                elif lo <= pos["sl"]:
                    exit_price, reason = pos["sl"], "SL"
                elif tp_mode in ("both", "fixed") and hi >= pos["tp"]:
                    exit_price, reason = pos["tp"], "TP"
            else:
                liq_price = pos["entry"] * (1 + liq_move / 100)
                if hi >= liq_price:
                    exit_price, reason = liq_price, "LIQUIDATED"
                elif hi >= pos["sl"]:
                    exit_price, reason = pos["sl"], "SL"
                elif tp_mode in ("both", "fixed") and lo <= pos["tp"]:
                    exit_price, reason = pos["tp"], "TP"
            if exit_price is not None:
                close_trade(i, exit_price, reason)
                pos = None
                require_hold = True  # engine calls reset_cross_state() here

            # EMA55-flip TP at candle close (original "BOTH" mode) + reverse
            if pos is not None and tp_mode in ("both", "flip"):
                if sig in ("BUY", "SELL") and sig != prev_sig and sig != pos["side"]:
                    close_trade(i, px, "EMA-FLIP")
                    new_side = "SHORT" if sig == "SELL" else "LONG"
                    pos = {"side": new_side, "entry": px,
                           "sl": px * (1 - sl_pct / 100) if new_side == "LONG"
                                 else px * (1 + sl_pct / 100),
                           "tp": px * (1 + tp_pct / 100) if new_side == "LONG"
                                 else px * (1 - tp_pct / 100)}
                    require_hold = False  # reset_for_reversal()

        # ---------- entry ----------
        if pos is None:
            if require_hold:
                if sig == "HOLD":
                    require_hold = False  # EMA55 left extreme position
            elif sig in ("BUY", "SELL") and sig != prev_sig:
                side = "LONG" if sig == "BUY" else "SHORT"
                entry = close[i]
                pos = {"side": side, "entry": entry,
                       "sl": entry * (1 - sl_pct / 100) if side == "LONG"
                             else entry * (1 + sl_pct / 100),
                       "tp": entry * (1 + tp_pct / 100) if side == "LONG"
                             else entry * (1 - tp_pct / 100)}

        prev_sig = sig

    if pos is not None:  # mark open position to market at the end
        close_trade(n - 1, close[-1], "END")
    return trades


def report(symbol: str, tf: str, df: pd.DataFrame, trades: list,
           lev: int, sl_pct: float, tp_pct: float) -> None:
    print(f"\n  --- {symbol} {tf} | EMA 8/13/21/55 original rules "
          f"(SL {sl_pct}% / TP {tp_pct}% or EMA55-flip) @ {lev}x ---")
    if not trades:
        print("  No trades.")
        return
    tdf = pd.DataFrame(trades)
    wins = tdf[tdf["net"] > 0]
    losses = tdf[tdf["net"] <= 0]
    wr = len(wins) / len(tdf) * 100
    total = tdf["roe"].sum()
    curve = tdf["roe"].cumsum()
    max_dd = (curve.cummax() - curve).max()
    pf = (wins["net"].sum() / abs(losses["net"].sum())
          if len(losses) and losses["net"].sum() != 0 else float("inf"))
    reasons = tdf["reason"].value_counts().to_dict()
    fees_paid = (tdf["roe"] / lev - tdf["net"]).sum() * lev / lev  # price-% of fees
    print(f"  Trades       : {len(tdf)}   Wins {len(wins)} / Losses {len(losses)}")
    print(f"  WIN RATE     : {wr:.1f}%")
    print(f"  Avg win/loss : {wins['net'].mean() if len(wins) else 0:+.3f}% / "
          f"{losses['net'].mean() if len(losses) else 0:+.3f}% price")
    print(f"  Profit factor: {pf:.2f}")
    print(f"  Total return : {total:+.1f}% ROE (per-trade margin, non-compounding)")
    print(f"  Max drawdown : {max_dd:.1f}% ROE")
    print(f"  Exits        : {reasons}")
    if "LIQUIDATED" in reasons:
        liq = tdf[tdf["reason"] == "LIQUIDATED"]
        print(f"  !! LIQUIDATIONS: {len(liq)} trades wiped to -100% ROE each")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--tf", default="4h")
    ap.add_argument("--bars", type=int, default=6_600)
    ap.add_argument("--years", type=float, help="approx years (overrides bars)")
    ap.add_argument("--sl-pct", type=float, default=2.0, help="original default 2")
    ap.add_argument("--tp-pct", type=float, default=6.0, help="original default 6")
    ap.add_argument("--fee", type=float, default=0.05)
    ap.add_argument("--tp-mode", default="both", choices=["both", "fixed", "flip"])
    ap.add_argument("--levs", default="10", help="comma list, e.g. 10,50,125")
    args = ap.parse_args()

    bars = args.bars
    if args.years:
        candles_per_day = 86_400_000 / {"1m": 60_000, "5m": 300_000, "15m": 900_000,
                                        "30m": 1_800_000, "1h": 3_600_000,
                                        "2h": 7_200_000, "4h": 14_400_000,
                                        "1d": 86_400_000}[args.tf]
        bars = int(args.years * 365 * candles_per_day)
    print(f"\nDownloading {args.symbol} {args.tf} x {bars} candles ...")
    raw = fetch_klines(args.symbol, args.tf, bars)
    df = precompute(raw)
    print(f"Data: {len(df)} candles | {df.index[0]} -> {df.index[-1]} | "
          f"fee {args.fee}%/side")

    for lev_s in args.levs.split(","):
        lev = int(lev_s.strip())
        trades = simulate(df, args.sl_pct, args.tp_pct, args.fee, lev,
                          args.tp_mode)
        report(args.symbol, args.tf, df, trades, lev, args.sl_pct, args.tp_pct)
