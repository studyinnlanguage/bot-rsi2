"""
RSI-2 Mean Reversion Backtest — REAL historical candles + fees
================================================================
Uses the bot's actual strategy module (bot.strategy.RSI2MeanReversionStrategy)
so the backtest tests EXACTLY what the live bot trades.

Simulation rules (same as engine):
- Entry at signal candle close (market order)
- SL: price-based (default 2% price move)
- TP: RSI exit (LONG: RSI >= 65, SHORT: RSI <= 35) checked on next candles
- Fees: taker per side (default 0.05% — Binance USDT-M; change via --fee)
- Leverage affects ROE%, not the price math

Usage:
  python tools/backtest_rsi2.py                          # BTCUSDT 1h, ~2 years
  python tools/backtest_rsi2.py --symbol ETHUSDT --tf 1h
  python tools/backtest_rsi2.py --tf 4h --years 3
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests

# Make the bot package importable (bot package lives in bot-engine/)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bot-engine"))

from bot.strategy import RSI2MeanReversionStrategy, Signal  # noqa: E402

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1/klines"
_TF_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
          "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "1d": 86_400_000}


def fetch_klines(symbol: str, interval: str, total: int) -> pd.DataFrame:
    """Download `total` candles from Binance USDT-M public API (paginated).
    Rate-limited: sleeps between batches, backs off on 418/429."""
    step = _TF_MS[interval]
    end = int(time.time() * 1000)
    frames = []
    remaining = total
    while remaining > 0:
        batch = min(remaining, 1000)
        start = end - batch * step
        data = None
        for attempt in range(6):
            r = requests.get(BINANCE_FAPI, params={
                "symbol": symbol, "interval": interval,
                "startTime": start, "endTime": end, "limit": 1000}, timeout=15)
            if r.status_code in (418, 429):
                wait = 10 * (attempt + 1)
                print(f"  [rate-limited {r.status_code}] waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            break
        if not data:
            break
        rows = [{"time": int(k[0]), "open": float(k[1]), "high": float(k[2]),
                 "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
                for k in data]
        frames.append(pd.DataFrame(rows))
        remaining -= len(rows)
        end = int(rows[0]["time"]) - step
        if len(rows) < batch:
            break
        time.sleep(1.2)  # stay under weight limits
    df = pd.concat(frames).drop_duplicates("time").sort_values("time")
    df = df.set_index(pd.to_datetime(df["time"], unit="ms")).drop(columns="time")
    return df[["open", "high", "low", "close", "volume"]]


def run_backtest(symbol: str, interval: str, total: int,
                 sl_pct: float = 3.0, fee_pct: float = 0.05,
                 leverage: int = 10, mode: str = "both") -> dict:
    df = fetch_klines(symbol, interval, total)
    print(f"\nData: {symbol} {interval} | {len(df)} candles | "
          f"{df.index[0]} -> {df.index[-1]}")
    print(f"Params: SL={sl_pct}% price | fees={fee_pct}%/side | lev={leverage}x | mode={mode}")

    strat = RSI2MeanReversionStrategy()

    position = None   # {"side": "LONG"/"SHORT", "entry": float, "sl": float}
    trades = []
    cooldown_until = None

    for i in range(len(df)):
        window = df.iloc[max(0, i - 600): i + 1]
        if len(window) < 210:
            continue
        res = strat.analyze(window)
        if res is None:
            continue
        price = res.last_close
        ts = window.index[-1]

        # --- manage open position ---
        if position is not None:
            hi = float(window.iloc[-1]["high"])
            lo = float(window.iloc[-1]["low"])
            close_now = float(window.iloc[-1]["close"])
            # fast exit EMA (mirrors strategy exit_ema_span=5)
            ema5 = window["close"].ewm(span=5, adjust=False).mean().iloc[-1]
            exit_price = None
            reason = None
            if position["side"] == "LONG":
                if lo <= position["sl"]:
                    exit_price, reason = position["sl"], "SL"
                elif close_now > ema5 or res.exit_long:
                    exit_price, reason = close_now, "EMA5/RSI-EXIT"
            else:
                if hi >= position["sl"]:
                    exit_price, reason = position["sl"], "SL"
                elif close_now < ema5 or res.exit_short:
                    exit_price, reason = close_now, "EMA5/RSI-EXIT"
            if exit_price is not None:
                direction = 1 if position["side"] == "LONG" else -1
                gross = (exit_price - position["entry"]) / position["entry"] * 100 * direction
                fees = fee_pct * 2  # entry + exit (per side % of notional)
                net = gross - fees
                roe = net * leverage
                trades.append({"time": ts, "side": position["side"], "entry": position["entry"],
                               "exit": exit_price, "gross_pct": gross, "net_pct": net,
                               "roe_pct": roe, "reason": reason})
                position = None
                cooldown_until = ts + pd.Timedelta(hours=1)
                # Live engine calls reset_cross_state() after every close:
                # RSI must return to the neutral band (30-70) before the
                # next entry is allowed. Replicate that here.
                strat.reset_cross_state()
                continue

        # --- entry (ONLY when flat - never replace an open position) ---
        if position is not None:
            continue
        if cooldown_until is not None and ts <= cooldown_until:
            continue
        if mode != "both" and ((mode == "long" and res.signal == Signal.SELL) or
                               (mode == "short" and res.signal == Signal.BUY)):
            continue
        if res.just_crossed and res.signal in (Signal.BUY, Signal.SELL):
            side = "LONG" if res.signal == Signal.BUY else "SHORT"
            sl = price * (1 - sl_pct / 100) if side == "LONG" else price * (1 + sl_pct / 100)
            position = {"side": side, "entry": price, "sl": sl}

    # ---- stats ----
    if not trades:
        print("\nNo trades generated — loosen thresholds or extend data range.")
        return {}
    tdf = pd.DataFrame(trades)
    wins = tdf[tdf["net_pct"] > 0]
    losses = tdf[tdf["net_pct"] <= 0]
    win_rate = len(wins) / len(tdf) * 100
    total_roe = tdf["roe_pct"].sum()
    max_dd = (tdf["roe_pct"].cumsum().cummax() - tdf["roe_pct"].cumsum()).max()

    print("\n" + "=" * 66)
    print(f"  BACKTEST RESULT — RSI-2 Mean Reversion ({symbol} {interval})")
    print("=" * 66)
    print(f"  Total trades      : {len(tdf)}")
    print(f"  Wins              : {len(wins)}   Losses: {len(losses)}")
    print(f"  WIN RATE          : {win_rate:.1f}%")
    print(f"  Avg win (net)     : {wins['net_pct'].mean():+.3f}% price  ({wins['roe_pct'].mean():+.1f}% ROE @{leverage}x)")
    print(f"  Avg loss (net)    : {losses['net_pct'].mean():+.3f}% price  ({losses['roe_pct'].mean():+.1f}% ROE @{leverage}x)")
    print(f"  Exit breakdown    : Strategy-EXIT {len(tdf[tdf['reason'] != 'SL'])} | SL {len(tdf[tdf['reason'] == 'SL'])}")
    print(f"  Total net return  : {total_roe:+.1f}% ROE (compounding off, per-trade margin basis)")
    print(f"  Max drawdown      : {max_dd:.1f}% ROE")
    pf = wins["net_pct"].sum() / abs(losses["net_pct"].sum()) if len(losses) and losses["net_pct"].sum() != 0 else float("inf")
    print(f"  Profit factor     : {pf:.2f}")
    print("=" * 66)
    print("\nNOTE: Simple non-compounding simulation. Real results vary with")
    print("slippage, funding and liquidity. Demo-test 2-4 weeks before live.")
    return {"win_rate": win_rate, "trades": len(tdf), "total_roe": total_roe}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--tf", default="4h", choices=list(_TF_MS))
    ap.add_argument("--bars", type=int, default=6_600, help="~3 years of 4h candles")
    ap.add_argument("--years", type=float, help="approx years (overrides bars)")
    ap.add_argument("--sl-pct", type=float, default=3.0)
    ap.add_argument("--fee", type=float, default=0.05, help="taker fee % per side")
    ap.add_argument("--lev", type=int, default=10)
    ap.add_argument("--mode", default="both", choices=["both", "long", "short"])
    args = ap.parse_args()
    bars = args.bars
    if args.years:
        bars = int(args.years * 365 * (86_400_000 / _TF_MS[args.tf]))
    run_backtest(args.symbol, args.tf, bars, args.sl_pct, args.fee, args.lev, args.mode)
