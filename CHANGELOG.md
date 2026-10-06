# Changelog

## v2.2 (Oct 2026) — Real Wallet Expectations (sizing study)

### Added
- **REAL WALLET EXPECTATIONS section** in BACKTEST_RESULTS.md: fixed-fractional
  sizing simulation on $100 (PRO 5-coin portfolio, 1326 trades, 3y).
  Sweet spot = ~2% wallet risk per trade -> +16-23%/yr, 57% months positive,
  maxDD ~37%. Full margin = ruin (variance drag). Entry-relaxation sweep
  (CUM 40/45/50, classic RSI<15/20/25) and 2h timeframe re-test: both lose
  edge vs PRO cum35 on 4h — confirms v2.1 config as the peak.
- README: REAL WALLET MATH note — honest daily/monthly expectations for
  buyers, scam-warning against $2-3/day claims (730-1100%/yr = martingale).

### Why
- Client question: "$100 wallet pe daily $2-3 possible?" — answered with
  data: no honest strategy can do it; expected value documented; sales
  messaging now includes realistic wallet math to protect buyers and seller.

## v2.1 (Oct 2026) — RSI-2 PRO + Verified Presets

### Added
- **Cumulative RSI-2 entry mode** (`rsi_cum`, default 35): Connors' original
  upgrade — entry when RSI(2) 2-bar sum < 35 above SMA200 (short mirror
  > 165). Grid-tested over 800 configs on BTC+ETH 4h; best robust config.
- **Longs-only mode** (`longs_only`): SAFE preset ke liye shorts off.
- **Dashboard presets**: PRO (BTC/ETH CUM-35), ALTCOIN (ADA/AVAX/SOL
  RSI<10), SAFE (longs-only) — 1-click auto-fill (strategy, SL 5%, 4h, 10x).
- **DEPLOY_AND_SALE.md** — VPS deploy + client sales playbook + FAQ.
- Replay verification: live strategy class vs backtest engine on BTC 4h
  3000 bars = identical trades (111/111, PF 1.26, WR 68.5%, 0% drift).

### Changed
- Default `stop_loss_pct` 3 → **5** (verified best for mean reversion).
- Default `rsi_cum` 35 (0 = classic mode), `longs_only` false.
- README rewritten with HONEST verified numbers (67-70% WR, PF 1.2-1.27),
  fee-tier guidance (MEXC/limit orders), rejected coins/timeframes list.
- BACKTEST_RESULTS.md: v2.1 optimization section (grid, 11-coin validation,
  6-year out-of-sample split, 1h recheck) prepended.

### Evidence highlights
- Fees are the #1 lever: taker 0.05% eats the edge (PF ~1.1), maker 0.02%
  solid (1.20-1.21), MEXC-class 0.00/0.01% best (1.24-1.27) on BTC/ETH.
- Coin selection beats tuning: ADA/AVAX/SOL good (ALTCOIN config),
  LINK/TRX/XRP/BNB/DOGE/memes lose with every config.
- 6y split: ETH consistent (PF 1.10/1.21), BTC regime-dependent
  (0.99 in 2020-23, 1.26 in 2023-26) — honesty documented.
- Timeframes: 5m/15m/1h lose even at low fees; 4h only recommendation.

## v2.0 (Oct 2026)
- RSI-2 mean reversion default strategy + 200-SMA filter
- MEXC adapter (mainnet), WEEX leverage fix, per-exchange max leverage
- Full/max leverage options, unlimited multi-coin, >20x consent popup
- Corrected backtest engine (position-replace bug disclosure + fix)
- EMA-vs-RSI2 evidence table

## v1.x (original)
- Quad-EMA 8/13/21/55 strategy, Binance/WEEX, trailing TP, SaaS layer
