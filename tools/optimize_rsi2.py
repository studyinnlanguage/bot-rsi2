"""
Deep RSI-2 optimizer — CORRECTED engine semantics (verified vs module engine)
=============================================================================
Levers tested on real Binance candles:
  - fee models: taker 0.05/side | maker-entry 0.02 | maker-both 0.02 | MEXC-like 0.00/0.01
  - entry: RSI(buy_below) plain or Connors cumulative-RSI (sum of 2 RSI-2 bars)
  - exit: fast (EMA5 cross) or RSI-recovery at 50/60/65
  - SL: 2/3/5/8% intrabar
  - longs_only toggle, time-stop, ATR-percentile regime filter
Semantics kept identical to live engine: entry only when flat, reset_cross_state
neutral-band re-arm (30-70) after close, 1h cooldown after close.

Usage:
  python scripts/optimize_rsi2.py --stage grid    # BTC+ETH 4h 3y full grid
  python scripts/optimize_rsi2.py --stage coins --cfg-file cfgs.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from backtest_rsi2 import fetch_klines  # noqa: E402  (same dir)

CACHE = Path(__file__).resolve().parent / "cache"
CACHE.mkdir(exist_ok=True)


def get_df(symbol: str, tf: str, bars: int) -> pd.DataFrame:
    fp = CACHE / f"{symbol}_{tf}_{bars}.csv"
    if fp.exists():
        df = pd.read_csv(fp, index_col=0, parse_dates=True)
        return df
    df = fetch_klines(symbol, tf, bars)
    df.to_csv(fp)
    time.sleep(0.9)
    return df


def wilder_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((loss == 0) & (gain > 0), 100.0)
    rsi = rsi.mask((gain == 0) & (loss > 0), 0.0)
    rsi = rsi.mask((gain == 0) & (loss == 0), 50.0)
    return rsi.clip(0, 100)


def run(df: pd.DataFrame, *, rsi_len=2, buy_below=10.0, sell_above=90.0,
        exit_long=65.0, exit_short=35.0, exit_mode="fast", sl_pct=3.0,
        fee_in=0.05, fee_out=0.05, lev=10, cum_rsi=None, trend_len=200,
        trend_type="sma", longs_only=False, time_stop=None,
        atr_q=None, cooldown_ms=3_600_000) -> dict:
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    n = len(df)
    if n < max(trend_len, 230):
        return {"trades": 0}

    rsi = wilder_rsi(df["close"], rsi_len).values
    if trend_type == "ema":
        trend = df["close"].ewm(span=trend_len, adjust=False).mean().values
    else:
        trend = df["close"].rolling(trend_len, min_periods=trend_len).mean().values
    e5 = df["close"].ewm(span=5, adjust=False).mean().values

    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    atr_pct = (atr / df["close"] * 100).values
    atr_thr = (pd.Series(atr_pct).rolling(500, min_periods=200)
               .quantile(atr_q / 100.0).values if atr_q else None)

    idx = df.index
    position = None
    prev_r = None
    require_neutral = False
    cooldown_until = 0
    trades = []

    start = max(trend_len, 209)
    for i in range(start, n):
        ts = idx[i].value // 10**6
        px, hi, lo = close[i], high[i], low[i]
        r, s = rsi[i], trend[i]
        if np.isnan(s):
            prev_r = r
            continue

        # ---------- manage open position ----------
        if position is not None:
            exit_price = reason = None
            position["age"] += 1
            if position["side"] == "LONG":
                if lo <= position["sl"]:
                    exit_price, reason = position["sl"], "SL"
                elif (px > e5[i] and exit_mode == "fast") or r >= exit_long:
                    exit_price, reason = px, "EXIT"
                elif time_stop and position["age"] >= time_stop:
                    exit_price, reason = px, "TIME"
            else:
                if hi >= position["sl"]:
                    exit_price, reason = position["sl"], "SL"
                elif (px < e5[i] and exit_mode == "fast") or r <= exit_short:
                    exit_price, reason = px, "EXIT"
                elif time_stop and position["age"] >= time_stop:
                    exit_price, reason = px, "TIME"
            if exit_price is not None:
                d = 1 if position["side"] == "LONG" else -1
                gross = (exit_price - position["entry"]) / position["entry"] * 100 * d
                net = gross - fee_in - fee_out
                trades.append({"net": net, "roe": net * lev, "reason": reason})
                position = None
                cooldown_until = ts + cooldown_ms
                require_neutral = True
                prev_r = None
                continue

        # ---------- entry (flat only) ----------
        elif ts > cooldown_until:
            blocked = (atr_thr is not None and
                       (np.isnan(atr_thr[i]) or atr_pct[i] > atr_thr[i]))
            if not blocked:
                if require_neutral:
                    if 30.0 <= r <= 70.0:
                        require_neutral = False
                else:
                    fresh_l = fresh_s = False
                    long_zone = short_zone = False
                    if cum_rsi is None:
                        long_zone = px > s and r < buy_below
                        short_zone = px < s and r > sell_above
                        fresh_l = prev_r is None or prev_r >= buy_below
                        fresh_s = prev_r is None or prev_r <= sell_above
                    else:
                        if prev_r is not None:
                            cum = r + prev_r
                            long_zone = px > s and cum < cum_rsi
                            short_zone = px < s and cum > (200.0 - cum_rsi)
                            fresh_l = cum < cum_rsi and (prev_r + rsi[i - 2]) >= cum_rsi
                            fresh_s = cum > (200.0 - cum_rsi) and \
                                (prev_r + rsi[i - 2]) <= (200.0 - cum_rsi)
                    if long_zone and fresh_l:
                        position = {"side": "LONG", "entry": px,
                                    "sl": px * (1 - sl_pct / 100), "age": 0}
                    elif short_zone and fresh_s and not longs_only:
                        position = {"side": "SHORT", "entry": px,
                                    "sl": px * (1 + sl_pct / 100), "age": 0}
        prev_r = r

    if not trades:
        return {"trades": 0}
    t = pd.DataFrame(trades)
    wins = t[t["net"] > 0]
    losses = t[t["net"] <= 0]
    pf = (wins["net"].sum() / abs(losses["net"].sum())
          if len(losses) and losses["net"].sum() != 0 else float("inf"))
    curve = t["roe"].cumsum()
    sl_n = int((t["reason"] == "SL").sum())
    return {"trades": len(t), "wr": len(wins) / len(t) * 100,
            "pf": pf, "roe": t["roe"].sum(),
            "dd": (curve.cummax() - curve).max(), "sl": sl_n}


FEE_MODELS = {
    "taker": (0.05, 0.05),      # worst case: market in, market out
    "mixed": (0.02, 0.05),      # limit entry (maker) + market exit
    "maker": (0.02, 0.02),      # limit in + limit out (Binance standard maker)
    "lowfee": (0.00, 0.01),     # MEXC-class fee tier
}


def grid_stage():
    tf, years = "4h", 3
    bars = int(years * 365 * (86_400_000 / 14_400_000))
    dfs = {}
    for sym in ("BTCUSDT", "ETHUSDT"):
        dfs[sym] = get_df(sym, tf, bars)
        print(f"loaded {sym}: {len(dfs[sym])} bars")

    results = []
    grid = list(itertools.product(
        FEE_MODELS.items(),
        (2.0, 3.0, 5.0, 8.0),                    # SL
        (("plain", None, 5.0), ("plain", None, 10.0), ("plain", None, 15.0),
         ("cum", 35.0, None), ("cum", 45.0, None)),  # entry variant, threshold
        ((50.0, "rsi"), (60.0, "rsi"), (65.0, "rsi"), (65.0, "fast"),
         (50.0, "fast")),                        # exit long threshold + mode
        (True, False),                           # longs_only
    ))
    print(f"grid size: {len(grid)} configs x 2 coins")

    for row in grid:
        (fee_name, (fee_in, fee_out)), sl, (ent_kind, cum_t, buy), \
            (ex, mode), lo = row
        kw = dict(sl_pct=sl, fee_in=fee_in, fee_out=fee_out,
                  exit_long=ex, exit_short=100.0 - ex,
                  exit_mode=mode, longs_only=lo,
                  buy_below=(buy if buy is not None else 10.0),
                  sell_above=(100.0 - buy) if buy is not None else 90.0)
        if ent_kind == "cum":
            kw["cum_rsi"] = cum_t
        r1 = run(dfs["BTCUSDT"], **kw)
        r2 = run(dfs["ETHUSDT"], **kw)
        if r1.get("trades", 0) < 40 or r2.get("trades", 0) < 40:
            continue
        score = min(r1["pf"], r2["pf"])
        ok = r1["roe"] > 0 and r2["roe"] > 0
        results.append({"fee": fee_name, "sl": sl, "entry": f"{ent_kind}{cum_t or buy}",
                        "exit": f"{ex}/{mode}", "lo": lo,
                        "btc_pf": r1["pf"], "btc_wr": r1["wr"], "btc_roe": r1["roe"],
                        "btc_tr": r1["trades"], "eth_pf": r2["pf"], "eth_wr": r2["wr"],
                        "eth_roe": r2["roe"], "eth_tr": r2["trades"],
                        "score": score, "ok": ok})

    res = pd.DataFrame(results).sort_values("score", ascending=False)
    res.to_csv("/home/z/my-project/cache/grid_results.csv", index=False)
    print("\n=== TOP 30 by min(BTC PF, ETH PF) ===")
    top = res.head(30)
    for _, r in top.iterrows():
        print(f"  {r['fee']:<6} SL{r['sl']:<4} ent {r['entry']:<7} "
              f"exit {r['exit']:<8} lo={int(r['lo'])} | "
              f"BTC {r['btc_tr']:>3}t PF{r['btc_pf']:.2f} WR{r['btc_wr']:4.1f}% "
              f"{r['btc_roe']:+7.1f}% | ETH {r['eth_tr']:>3}t PF{r['eth_pf']:.2f} "
              f"WR{r['eth_wr']:4.1f}% {r['eth_roe']:+7.1f}%")
    print(f"\nconfigs with BOTH coins profitable: {int(res['ok'].sum())} / {len(res)}")


def coins_stage():
    tf, years = "4h", 3
    bars = int(years * 365 * (86_400_000 / 14_400_000))
    coins = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
             "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "TRXUSDT",
             "DOGEUSDT", "PEPEUSDT")
    configs = {
        "WINNER cum35/SL5/ex65fast": dict(cum_rsi=35.0, sl_pct=5.0,
                                          exit_long=65.0, exit_short=35.0,
                                          exit_mode="fast"),
        "SAFE cum35/SL5/ex65/long-only": dict(cum_rsi=35.0, sl_pct=5.0,
                                              exit_long=65.0, exit_short=35.0,
                                              exit_mode="fast", longs_only=True),
        "LEGACY rsi10/SL5/ex65fast": dict(sl_pct=5.0, buy_below=10.0,
                                          sell_above=90.0, exit_long=65.0,
                                          exit_short=35.0, exit_mode="fast"),
    }
    fee_sets = {"maker(0.02/0.02)": (0.02, 0.02),
                "lowfee(0.00/0.01)": (0.00, 0.01),
                "taker(0.05/0.05)": (0.05, 0.05)}
    print(f"loading {len(coins)} coins ...")
    dfs = {}
    for sym in coins:
        try:
            dfs[sym] = get_df(sym, tf, bars)
            print(f"  {sym}: {len(dfs[sym])} bars")
        except Exception as e:
            print(f"  {sym}: SKIP ({str(e)[:50]})")

    for fee_name, (fin, fout) in fee_sets.items():
        print(f"\n=== fee model {fee_name} ===")
        print(f"  {'coin':<10} | " + " | ".join(
            f"{c.split()[0]:>24}" for c in configs))
        agg = {k: {"pf_sum": 0.0, "n": 0, "pos": 0, "roe_sum": 0.0}
               for k in configs}
        for sym, df in dfs.items():
            cells = []
            for cname, kw in configs.items():
                r = run(df, fee_in=fin, fee_out=fout, lev=10, **kw)
                if r.get("trades", 0) < 25:
                    cells.append(f"{'n/a':>24}")
                    continue
                cells.append(f"{r['trades']:>3}t PF{r['pf']:.2f} "
                             f"WR{r['wr']:4.1f}% {r['roe']:+6.0f}%")
                agg[cname]["pf_sum"] += r["pf"]
                agg[cname]["roe_sum"] += r["roe"]
                agg[cname]["n"] += 1
                agg[cname]["pos"] += 1 if r["roe"] > 0 else 0
            print(f"  {sym:<10} | " + " | ".join(cells))
        print("  --- aggregates ---")
        for cname, a in agg.items():
            if a["n"]:
                print(f"  {cname:<30} avg PF {a['pf_sum']/a['n']:.2f} | "
                      f"avg ROE {a['roe_sum']/a['n']:+.0f}% | "
                      f"{a['pos']}/{a['n']} coins profitable")


def split_stage():
    """Out-of-sample honesty check: 6y of 4h data, run on first and second 3y."""
    tf = "4h"
    bars = int(6 * 365 * (86_400_000 / 14_400_000))
    configs = {
        "WINNER cum35/SL5": dict(cum_rsi=35.0, sl_pct=5.0, exit_long=65.0,
                                 exit_short=35.0, exit_mode="fast"),
        "SAFE cum35/SL5/lo": dict(cum_rsi=35.0, sl_pct=5.0, exit_long=65.0,
                                  exit_short=35.0, exit_mode="fast",
                                  longs_only=True),
    }
    for sym in ("BTCUSDT", "ETHUSDT"):
        df = get_df(sym, tf, bars)
        half = len(df) // 2
        h1, h2 = df.iloc[:half], df.iloc[half - 200:]
        print(f"\n{sym} 6y split: {df.index[0].date()} -> {df.index[-1].date()} "
              f"({len(df)} bars)")
        print(f"  H1: {h1.index[0].date()} -> {h1.index[-1].date()} | "
              f"H2: {h2.index[0].date()} -> {h2.index[-1].date()}")
        for cname, kw in configs.items():
            for part_name, part in (("H1", h1), ("H2", h2)):
                for fee_name, (fin, fout) in (("maker", (0.02, 0.02)),
                                              ("taker", (0.05, 0.05))):
                    r = run(part, fee_in=fin, fee_out=fout, lev=10, **kw)
                    if r.get("trades", 0) < 15:
                        print(f"  {cname:<18} {part_name} {fee_name:<5} "
                              f"too few trades")
                        continue
                    print(f"  {cname:<18} {part_name} {fee_name:<5} "
                          f"{r['trades']:>3}t PF{r['pf']:.2f} WR{r['wr']:4.1f}% "
                          f"{r['roe']:+7.1f}% DD{r['dd']:.0f}%")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="grid")
    args = ap.parse_args()
    if args.stage == "grid":
        grid_stage()
    elif args.stage == "coins":
        coins_stage()
    elif args.stage == "split":
        split_stage()
