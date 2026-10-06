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

## Live Signal Monitor (keyless paper trading)

Runs the bot's actual strategy module on live exchange candles with virtual
positions, SL and fees — no API keys needed:

```bash
python3 tools/live_signal_monitor.py --tf 4h --tag 4h --interval 60
python3 tools/live_signal_monitor.py --tf 15m --tag 15m --interval 60
```

Logs: `/logs/live_monitor_*.log`, virtual trades: `/logs/live_trades_*.json`
