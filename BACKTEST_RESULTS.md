# RSI-2 Backtest Results — CORRECTED + OPTIMIZED (Oct 2026, v2.1)

## OPTIMIZATION v2.1 — final verified config (read this first)

800-config grid on BTC+ETH 4h (3y) with the corrected engine, then 11-coin
validation, then a 6-year out-of-sample split. Engine semantics = live bot
(flat-only entries, neutral-band re-arm, 1h cooldown, intrabar SL).

### Fee models decide everything

| Fee model (entry/exit %) | BTC PF | ETH PF | Verdict |
|---|---|---|---|
| taker 0.05/0.05 (market orders, Binance default) | 1.09 | 1.12 | edge mostly eaten |
| maker 0.02/0.02 (limit orders) | 1.21 | 1.20 | solid |
| low-fee 0.00/0.01 (MEXC futures class) | **1.27** | **1.24** | best |

Mean reversion is fee-sensitive by nature: use limit/post-only entries or a
low-fee exchange. This is the single biggest lever we found.

### Verified presets (4h, 10x, SL 5%, 2023-2026)

| Preset | Coins | Config | PF maker | PF lowfee | WR | 3y ROE (lowfee) |
|---|---|---|---|---|---|---|
| **PRO** | BTC, ETH | CUM RSI-35 entry, exit RSI>=65 or close>EMA5 | 1.21 / 1.20 | 1.27 / 1.24 | 67-70% | BTC +359%, ETH +504% |
| **ALTCOIN** | ADA, AVAX, SOL | classic RSI<10 entry, exit RSI>=65/EMA5 | 1.21 / 1.15 / 1.10 | 1.24 / 1.18 / 1.13 | 63-66% | ADA +651%, AVAX +548%, SOL +409% |
| **SAFE** | BTC, ETH | PRO + longs-only | higher WR (69-72%) | — | 69-72% | lower total (shorts carried profit in 2023-26) |

Rejected coins (lose with ANY config, all fee models): **LINK, TRX, XRP, BNB,
DOGE, memes**. Coin selection matters more than parameter tuning.

### 6-year out-of-sample split (4h, 10x, maker fees, CUM35/SL5)

| Coin | H1 2020-23 | H2 2023-26 | Honest read |
|---|---|---|---|
| BTC | PF 0.99 (-14%) | PF 1.26 (+355%) | regime-dependent: dead 2020-23, strong 2023-26 |
| ETH | PF 1.10 (+304%) | PF 1.21 (+458%) | consistent across 6 years |

Max drawdowns are deep (up to ~45% of margin at 10x on the ROE curve). No
guarantee the 2023-26 regime persists.

### Timeframe re-check with optimized config

| TF | BTC | ETH | Verdict |
|---|---|---|---|
| 1h (2y, maker) | PF 0.97 | PF 0.88 | still loses |
| 1h (2y, 0-fee) | PF 1.08 | PF 0.95 | not robust |
| 4h | best | best | **only recommended TF** |

5m/15m confirmed losing earlier. 4h remains the ONLY recommended timeframe.

### Bottom line for v2.1

- Best honest, verified setup: **PRO preset, BTC+ETH, 4h, 10x, low fees**
  → PF ~1.2-1.27, WR ~67-70%, roughly +120%/year on ROE at 10x in 2023-26,
  with deep drawdowns and no guarantee of persistence.
- At 0.05% taker fees the same strategy is marginal — sell the bot as a TOOL,
  never as a guaranteed profit machine.
- The live class was replay-verified against this engine on BTC 4h:
  **identical trades (111/111, PF 1.26, WR 68.5%)**.

---

## Historical: original corrected analysis (v2.0, before optimization)

## Bug disclosure (read this first)

The results previously published in this file (Oct 6, commit 5a517d9) were
**INFLATED by a simulation bug**: the backtester let a fresh signal REPLACE an
open virtual position without booking the replaced trade's loss, and it skipped
the live engine's post-close `reset_cross_state()` (RSI must return to the
neutral 30-70 band before the next entry). The live bot takes ONE position per
symbol and respects the neutral reset — the corrected tool now replicates that
exactly. Every number below is corrected.

## Timeframe comparison — BTCUSDT (3y real candles, fees 0.05%/side, SL 3%, 10x)

| Timeframe | Trades | Win Rate | Profit Factor | Total Return |
|---|---|---|---|---|
| 5m (3 months) | 686 | 24.2% | 0.21 | **-576%** |
| 15m (1 year) | 1187 | 47.9% | 0.57 | **-830%** |
| 1h (3 years) | 966 | 58.7% | 0.67 | **-1120%** |
| **4h (3 years)** | 248 | 62.9% | **0.90** | **-176%** |
| 1d (3 years) | 33 | 48.5% | 0.74 | **-138%** |

ETH shows the same shape (4h: 285 trades, 64.9% WR, PF 1.01, +35.0%).
Lower timeframe = more trades x fees = death. 4h is the least-bad.

## Parameter scan (4h, 3y, BTC + ETH, corrected)

| Variant | BTC PF | ETH PF |
|---|---|---|
| SL 1.5% | 0.82 | 0.86 |
| SL 2% | 0.90 | 0.95 |
| SL 3% (default) | 0.90 | 1.01 |
| **SL 5%** | **1.07** (+100.8% ROE/3y) | **1.01** (+35.8% ROE/3y) |
| SL 8% | 1.04 | 0.95 |
| RSI-only exit (no EMA5 fast exit) | 0.90 | 1.03 |

Best found = wider SL (5%) — fewer whipsaw stop-outs. Still only marginal.

## 18-coin sweep (4h, 3 years, SL 5%, corrected engine)

| Coin | PF | Return | | Coin | PF | Return |
|---|---|---|---|---|---|---|
| ADA | **1.15** | +423% | | LTC | 0.98 | -57% |
| BTC | 1.07 | +101% | | DOGE | 0.94 | -203% |
| OP | 1.07 | +255% | | 1000PEPE | 0.93 | -318% |
| SOL | 1.05 | +160% | | BNB | 0.88 | -228% |
| ETH | 1.01 | +36% | | SUI | 0.86 | -553% |
| AVAX | 1.00 | +6% | | XRP | 0.83 | -492% |
| ARB | 0.92 | -310% | | LINK | 0.74 | -947% |
| APT | 0.89 | -421% | | TRX | 0.54 | -863% |
| NEAR | 0.90 | -405% | | DOT | 0.90 | -319% |

## Honest conclusions (rewritten)

1. **After taker fees, RSI-2 with these rules is break-even at best on 4h.**
   All lower timeframes (5m/15m/1h) LOSE badly. The earlier "+380-590% ROE,
   70-72% WR" claims were the bug's artifact — verified win rate is 60-65%,
   profit factor 0.9-1.07.
2. Of 18 coins tested, only ADA clears PF 1.15 (best-of-18 sample, likely
   luck); BTC/OP/SOL/ETH/AVAX are marginal (1.00-1.07); 12 coins lose.
3. Meme coins (PEPE, DOGE) lose — confirmed again on corrected data.
4. Live results will be WORSE than backtest: funding rates (perps), slippage,
   and partial fills are NOT in these numbers.
5. Realistic expectation at 10x on the best config: roughly +1-3% per month
   average on margin, with 250-500% ROE drawdowns along the way — i.e. **no
   meaningful edge after costs**. Do NOT run this live with money you cannot
   afford to lose. Paper trade first.
6. The old EMA 8/13/21/55 strategy is far worse (see section below).
7. If a higher fee tier / worse fills apply to your account, subtract ~0.1%
   round-trip notional per trade from every result above.

## EMA 8/13/21/55 (old strategy) vs RSI-2 — same data, same fees

Old bot rules replicated exactly: fresh EMA55-cross entry, SL 2%, TP 6% OR
EMA55-flip close + reverse, `reset_cross_state` wait after SL/TP close.
Fees 0.05%/side. Liquidation model included for high leverage.
(This tool never had the replacement bug — entries only when flat.)

Reproduce: `python3 tools/backtest_ema.py --symbol BTCUSDT --tf 4h --years 3`

| Config (original bot settings) | Trades | Win Rate | Profit Factor | Total Return | Max DD |
|---|---|---|---|---|---|
| BTC 5m, 3 months, 10x (original default TF) | 662 | **22.4%** | 0.56 | **-777%** | 775% |
| BTC 5m, 3 months, 50x | 662 | 22.4% | 0.56 | -3,896% | 4 liquidations |
| BTC 5m, 3 months, 125x | 632 | 19.3% | 0.53 | **-9,437%** | **167 liquidations** |
| BTC 1h, 1 year, 10x | 175 | 33.7% | 1.07 | +105% | 244% |
| BTC 4h, 3 years, 10x (EMA best case) | 131 | 30.5% | 1.11 | +199% | 260% |
| ETH 4h, 3 years, 10x | 147 | 27.2% | 0.97 | **-78%** | 394% |

Why the old strategy lost:
1. **5m whipsaw**: 662 trades in 3 months, 654 closed by EMA-flip (enter ->
   whipsaw -> flip -> re-enter). 22% win rate; fees + churn bleed the account.
2. **125x leverage**: liquidation at ~0.4% adverse move — 167 of 632 trades
   were liquidated to -100% each before the 2% SL could ever fire.
3. **Even at its best (BTC 4h)** only 30.5% of trades win — 7 of 10 trades are
   losses, with long losing streaks (260% ROE drawdown). On ETH it loses net.
4. Real-data check on the user's own dashboard coin (1000000MOGUSDT 5m, 50x):
   99 trades / 14 days, PF 0.70, -1,115% ROE, **17 liquidations**.

## Live Signal Monitor (keyless paper trading)

Runs the bot's actual strategy module on live exchange candles with virtual
positions, SL and fees — no API keys needed. The monitor uses the CORRECT
live semantics (one position per symbol + reset_cross_state after close).

```bash
python3 tools/live_signal_monitor.py --tf 4h --tag 4h --interval 60
python3 tools/live_signal_monitor.py --tf 15m --tag 15m --interval 60
```

Logs: `/logs/live_monitor_*.log`, virtual trades: `/logs/live_trades_*.json`

Reproduce corrected backtests:
```bash
python3 tools/backtest_rsi2.py --symbol BTCUSDT --tf 4h --years 3
python3 tools/backtest_ema.py --symbol BTCUSDT --tf 4h --years 3
```