# RSI-2 Backtest Results — Multi-Coin Verification (Oct 2026)

**Setup:** 3 years real Binance USDT-M candles (2023-10-01 → 2026-10-06), 4h timeframe,
10x leverage, 3% price SL, taker fees 0.05%/side included, non-compounding per-trade margin.

Reproduce: `python3 tools/backtest_rsi2.py --symbol ETHUSDT`

## Results

| Coin | Trades | Win Rate | Avg Win | Avg Loss | Profit Factor | Total Return | Max Drawdown |
|-------|--------|----------|---------|----------|---------------|--------------|--------------|
| BTCUSDT | 263 | **71.9%** | +9.9% ROE | -20.0% ROE | **1.26** | **+379.7% ROE** | 157.9% ROE |
| ETHUSDT | 307 | **69.1%** | +13.9% ROE | -24.7% ROE | **1.25** | **+587.5% ROE** | 253.9% ROE |
| SOLUSDT | 302 | 61.6% | +18.2% ROE | -27.8% ROE | 1.05 | +164.4% ROE | 589.5% ROE |
| BNBUSDT | 260 | 68.8% | +10.3% ROE | -21.4% ROE | 1.06 | +99.9% ROE | 389.6% ROE |
| XRPUSDT | 279 | 64.2% | +15.0% ROE | -26.3% ROE | 1.03 | +65.9% ROE | 334.5% ROE |
| DOGEUSDT | 282 | 56.4% | +20.5% ROE | -28.0% ROE | **0.94** | **-191.8% ROE** | 433.1% ROE |

## Honest Conclusions

1. **RSI-2 mean reversion works BEST on BTC & ETH** (PF 1.25-1.26, ~70% win rate).
2. SOL / BNB / XRP: marginally profitable after fees — use small position size only.
3. **DOGE / meme coins: strategy LOSES money** — mean reversion fails on
   strongly trending, meme-driven coins. DO NOT trade meme coins with this bot.
4. Recommended watchlist: **BTCUSDT + ETHUSDT** (core), optionally BNB/SOL/XRP small size.
5. Max drawdown is large relative to per-trade margin — use **% of wallet sizing
   with 5-10% per trade** so a drawdown never threatens the account.
6. Verified win rate is **~70%, not 80-90%** (YouTube claims are marketing).
7. Always demo-test 2-4 weeks before live trading.

## EMA 8/13/21/55 (old strategy) vs RSI-2 — same data, same fees

Old bot rules replicated exactly: fresh EMA55-cross entry, SL 2%, TP 6% OR
EMA55-flip close + reverse, `reset_cross_state` wait after SL/TP close.
Fees 0.05%/side. Liquidation model included for high leverage.

Reproduce: `python3 tools/backtest_ema.py --symbol BTCUSDT --tf 4h --years 3`

| Config (original bot settings) | Trades | Win Rate | Profit Factor | Total Return | Max DD |
|---|---|---|---|---|---|
| BTC 5m, 3 months, 10x (original default TF) | 662 | **22.4%** | 0.56 | **-777%** | 775% |
| BTC 5m, 3 months, 50x | 662 | 22.4% | 0.56 | -3,896% | 4 liquidations |
| BTC 5m, 3 months, 125x | 632 | 19.3% | 0.53 | **-9,437%** | **167 liquidations** |
| BTC 1h, 1 year, 10x | 175 | 33.7% | 1.07 | +105% | 244% |
| BTC 4h, 3 years, 10x (EMA best case) | 131 | 30.5% | 1.11 | +199% | 260% |
| ETH 4h, 3 years, 10x | 147 | 27.2% | 0.97 | **-78%** | 394% |
| **RSI-2 BTC 4h, 3y, 10x** | 263 | **71.9%** | **1.26** | **+380%** | 158% |
| **RSI-2 ETH 4h, 3y, 10x** | 307 | **69.1%** | **1.25** | **+588%** | 254% |

Why the old strategy lost:
1. **5m whipsaw**: 662 trades in 3 months, 654 closed by EMA-flip (enter ->
   whipsaw -> flip -> re-enter). 22% win rate; fees + churn bleed the account.
2. **125x leverage**: liquidation at ~0.4% adverse move — 167 of 632 trades
   were liquidated to -100% each before the 2% SL could ever fire.
3. **Even at its best (BTC 4h)** only 30.5% of trades win — 7 of 10 trades are
   losses, with long losing streaks (260% ROE drawdown). On ETH it loses net.

## Live Signal Monitor (keyless paper trading)

Runs the bot's actual strategy module on live exchange candles with virtual
positions, SL and fees — no API keys needed:

```bash
python3 tools/live_signal_monitor.py --tf 4h --tag 4h --interval 60
python3 tools/live_signal_monitor.py --tf 15m --tag 15m --interval 60
```

Logs: `/logs/live_monitor_*.log`, virtual trades: `/logs/live_trades_*.json`
