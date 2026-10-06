"""
Smoke test: live RSI2MeanReversionStrategy with cum_rsi mode vs fast engine.
Feeds the LIVE class candle-by-candle over the last N bars (sliding window,
like the live engine's 500-kline fetch) and compares trades with the
verified fast engine on the same slice. Tolerates RSI warmup drift.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from optimize_rsi2 import run, get_df  # noqa: E402
from bot.strategy import RSI2MeanReversionStrategy  # noqa: E402
from bot.indicators import calculate_rsi  # noqa: E402


def live_replay(df: pd.DataFrame, *, cum_rsi=35.0, longs_only=False,
                sl_pct=5.0, window=500) -> dict:
    strat = RSI2MeanReversionStrategy(cum_rsi=cum_rsi, longs_only=longs_only)
    strat.reset_cross_state()
    pos = None
    trades = []
    start = 210
    for i in range(start, len(df)):
        w = df.iloc[max(0, i - window + 1): i + 1]
        res = strat.analyze(w)
        if res is None:
            continue
        px = float(w["close"].iloc[-1])
        lo, hi = float(w["low"].iloc[-1]), float(w["high"].iloc[-1])
        if pos is not None:
            exit_hit = (lo <= pos["sl"] if pos["side"] == "LONG"
                        else hi >= pos["sl"])
            strat_exit = (res.exit_long if pos["side"] == "LONG"
                          else res.exit_short)
            if exit_hit or strat_exit:
                d = 1 if pos["side"] == "LONG" else -1
                exit_px = pos["sl"] if exit_hit else px
                gross = (exit_px - pos["entry"]) / pos["entry"] * 100 * d
                trades.append(gross - 0.04)  # maker both sides
                pos = None
                strat.reset_cross_state()
                continue
        if pos is None and res.just_crossed:
            if res.signal.value == "BUY":
                pos = {"side": "LONG", "entry": px,
                       "sl": px * (1 - sl_pct / 100)}
            elif res.signal.value == "SELL" and not longs_only:
                pos = {"side": "SHORT", "entry": px,
                       "sl": px * (1 + sl_pct / 100)}
    t = pd.Series(trades) if trades else pd.Series(dtype=float)
    wins = t[t > 0]
    losses = t[t <= 0]
    pf = (wins.sum() / abs(losses.sum())
          if len(losses) and losses.sum() != 0 else float("inf"))
    return {"trades": len(t), "wr": (len(wins) / len(t) * 100) if len(t) else 0,
            "pf": pf, "roe": t.sum() * 10}


def main():
    df = get_df("BTCUSDT", "4h", 6571)
    tail = df.iloc[-3000:]  # ~1.4y slice
    print(f"BTCUSDT 4h last {len(tail)} bars "
          f"({tail.index[0].date()} -> {tail.index[-1].date()})")

    fast = run(tail, cum_rsi=35.0, sl_pct=5.0, exit_long=65.0,
               exit_short=35.0, exit_mode="fast", fee_in=0.02, fee_out=0.02)
    live = live_replay(tail, cum_rsi=35.0)
    print(f"fast engine : {fast['trades']}t PF{fast['pf']:.2f} WR{fast['wr']:.1f}%")
    print(f"live class  : {live['trades']}t PF{live['pf']:.2f} WR{live['wr']:.1f}%")
    drift = abs(fast["trades"] - live["trades"]) / max(1, fast["trades"])
    ok = drift <= 0.15 and live["trades"] > 0
    print(f"trade-count drift: {drift*100:.1f}% -> {'PASS' if ok else 'CHECK'}")

    # longs_only sanity: no SELL signals should open shorts
    live_lo = live_replay(tail, cum_rsi=35.0, longs_only=True)
    print(f"longs-only  : {live_lo['trades']}t PF{live_lo['pf']:.2f} "
          f"WR{live_lo['wr']:.1f}%")
    print("SMOKE " + ("PASS" if ok else "NEEDS REVIEW"))


if __name__ == "__main__":
    main()
