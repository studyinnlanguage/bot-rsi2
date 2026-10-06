# TradeBot SaaS v2.2 — RSI-2 PRO (Multi-Exchange Trading Bot + Cloud Panel)

**Sale-ready crypto futures bot** — Larry Connors ki RSI-2 mean reversion
strategy (cumulative-RSI PRO mode ke sath), 3 exchanges, web dashboard,
verified presets, aur poori SaaS billing layer (users, trials, subscriptions,
admin panel, referrals, licenses).

> ⚠️ **HONEST PERFORMANCE NOTE (pehle ye parho):** Verified backtest
> (2023-2026, real candles, fees included, 10x): BTC/ETH 4h par
> **~67-70% win rate, profit factor 1.2-1.27**. Ye 90% win rate nahi hai —
> koi bhi genuine bot 90% nahi deta. Deep drawdowns aate hain aur past
> performance future ki guarantee nahi. Bot ko **tool** ki tarah becho,
> "guaranteed profit machine" ki tarah kabhi nahi.

> 💰 **REAL WALLET MATH (v2.2 sizing study):** Proper risk-sizing (har trade
> pe wallet ka ~2% risk) ke sath $100 wallet realistic: **+16-23% per year**
> (3 saal me $100 -> $155-182), average **~$0.05-0.08/day**. PRO 5-coin
> portfolio me ~37 trades/month (1.2/day), 57% months positive, worst month
> -19%, max drawdown ~37%. **$2-3/day on $100 (730-1100%/year) koi real
> strategy nahi de sakta** — jo bole wo martingale/scam hai. Is edge pe
> $2-3/day ke liye $3,000-6,000 wallet chahiye. Full details:
> BACKTEST_RESULTS.md → "REAL WALLET EXPECTATIONS".

---

## ✨ Features (Sale Points)

### Strategy Engine
- **RSI-2 Mean Reversion PRO** — Connors cumulative-RSI entry (RSI[2] 2-bar
  sum < 35) + 200-SMA trend filter + dual exit (RSI≥65 ya EMA5 bounce) +
  strict 5% SL. Live engine = verified backtest engine (111/111 trades
  identical replay).
- **ALTCOIN mode** — classic RSI<10 entry (ADA/AVAX/SOL ke liye verified best).
- **SAFE mode** — longs-only (shorts off, higher win rate).
- **Legacy EMA 8/13/21/55** crossover bhi included (2 strategies 1 bot).
- One position per coin, anti-immediate-reentry neutral reset, 1h cooldown,
  intrabar stop-loss watchdog.

### Exchanges (sab futures, mainnet + testnet*)
- **Binance USDT-M** — full leverage 1-125x
- **WEEX** — leverage 1-500x
- **MEXC** — leverage 1-200x (best fees: 0.00% maker / 0.01% taker —
  PRO preset ke liye recommended)
- (*MEXC sirf mainnet — MEXC ka public demo nahi hota)
- Unlimited multi-coin watchlist, per-exchange max-leverage enforcement,
  >20x leverage par informed-consent warning popup.

### Dashboard (browser, mobile PWA)
- Live candles chart (lightweight-charts) + EMA overlay
- **1-click verified presets**: PRO / ALTCOIN / SAFE
- Full RSI-2 parameter control (period, SMA, cum threshold, exits, SL)
- Trailing TP (1:1 → 1:2 → 1:3 auto-ratchet + break-even) / RSI-exit /
  EMA-reversal modes
- Telegram / Email / WhatsApp notifications
- Position, PnL, logs, start/stop — sab UI se

### SaaS Layer (tumhare server pe)
- User signup/login, **7-day free trial**, subscriptions (Basic/Pro/Lifetime)
- Admin panel: users, extend/ban/delete, licenses, debug logs
- Per-user bot isolation (alag process/port), API keys encrypted
- Referral + payout system, payment page, license activation
- PM2 24/7 + Cloudflare tunnel public URL + Railway/Docker files

---

## 📊 Verified Performance (real data, fees included)

| Preset | Coins | WR | PF (maker) | PF (MEXC-class fees) | 3y ROE @10x |
|---|---|---|---|---|---|
| **PRO** (CUM RSI-35, SL 5%) | BTC | 67-69% | 1.21 | **1.27** | +359% |
| | ETH | 70% | 1.20 | **1.24** | +504% |
| **ALTCOIN** (RSI<10, SL 5%) | ADA | 66% | 1.21 | 1.24 | +651% |
| | AVAX | 67% | 1.15 | 1.18 | +548% |
| | SOL | 65% | 1.10 | 1.13 | +409% |
| **SAFE** (longs-only) | BTC/ETH | 69-72% | — | — | lower (stable) |

**Kaise parhein:** 10x leverage par +359% ROE / 3y ≈ margin par ~120%/year.
Max drawdown ROE curve par ~40%+ margin tak — iske liye tayyar raho.

**Rejected coins** (har config mein loss): LINK, TRX, XRP, BNB, DOGE, memes.
**Rejected timeframes**: 5m / 15m / 1h (fees + noise) — **sirf 4h use karo**.

Full tables + methodology: [`BACKTEST_RESULTS.md`](BACKTEST_RESULTS.md)

### Fees = sab kuch
| Order type | Fee/side | Result |
|---|---|---|
| Market (taker) | 0.05% | edge ~khatam |
| Limit (maker) | 0.02% | solid |
| MEXC | 0.00-0.01% | best |

**Rule: PRO preset MEXC pe chalao, ya Binance pe limit entries use karo.**

---

## 🚀 Quick Start (VPS)

```bash
scp repo.zip user@server:~/ && ssh user@server
unzip repo.zip && cd bot-rsi2 && chmod +x install.sh && ./install.sh
cloudflared tunnel --url http://localhost:5000   # public URL
```

Admin panel: `https://your-url/admin` (password `.env` mein `ADMIN_SECRET`)

## 👤 Client Flow (Sale ke waqt)

1. Client ko public URL do → Sign Up (7-day trial auto)
2. Dashboard → Settings: exchange (MEXC recommended), API keys, coins
   (**BTC + ETH only**), **PRO preset click**, leverage 10x, Save
3. Testnet se verify karo → phir mainnet chalu
4. Trial khatam → tum admin panel se subscription extend karo

## 💰 Suggested Pricing

| Plan | Price | Duration |
|---|---|---|
| Trial | FREE | 7 days |
| Monthly | $30 | 30 days |
| Quarterly | $75 | 90 days |
| Yearly | $250 | 365 days |
| Lifetime | $400 | forever |

Sales playbook + client FAQ: [`DEPLOY_AND_SALE.md`](DEPLOY_AND_SALE.md)

## 🔒 Security

- API keys encrypted (XOR+base64, per-install key), passwords salted-hash
- Per-user process isolation, session auth (7-day), admin protected
- Exchange-side SL attached + software watchdog (double layer)

## 🧪 Backtesting Tools (included — clients ko bhi trust dilao)

```bash
cd bot-engine/tools
python backtest_rsi2.py --symbol BTCUSDT            # RSI-2 official tool
python backtest_ema.py --symbol BTCUSDT             # purani EMA vs RSI-2
python live_signal_monitor.py                       # live signal tracker
```

## 📁 Structure

```
bot-rsi2/
├── app.py                  ← SaaS layer (users, billing, admin, referrals)
├── install.sh              ← one-command VPS install
├── bot-engine/
│   ├── app.py              ← bot API + config validation (presets, rsi_cum)
│   ├── bot/
│   │   ├── strategy.py     ← RSI-2 PRO (cum mode) + legacy EMA
│   │   ├── engine.py       ← trading engine, strategy selector
│   │   ├── trader.py       ← Binance adapter
│   │   ├── weex_trader.py  ← WEEX adapter
│   │   ├── mexc_trader.py  ← MEXC adapter
│   │   └── notifier.py     ← Telegram/Email/WhatsApp
│   ├── templates/dashboard.html ← trading dashboard (presets UI)
│   ├── static/             ← PWA assets
│   └── tools/              ← backtest + monitor tools
├── BACKTEST_RESULTS.md     ← full evidence (methodology + tables)
├── DEPLOY_AND_SALE.md      ← sales playbook
└── CHANGELOG.md
```

## ⚠️ Risk Disclosure (clients ko bhi yehi bolo)

1. Crypto futures leverage trading mein **poora margin doob sakta hai**.
2. Is bot ka verified edge ~67-70% WR / PF 1.2 hai — **losses aayenge**,
   strategy unhe drawdown mein manage karti hai.
3. 50x-125x leverage + meme coins = liquidation (humne real data se prove
   kiya hai — BACKTEST_RESULTS.md dekho). Bot defaults 10x hain, isse
   mat badlo jab tak risk samajh na ho.
4. Pehle **testnet**, phir chhoti amount, phir badhao.

---

**v2.1** — RSI-2 PRO (cumulative) + verified presets + 3 exchanges + SaaS.
Live engine replay-verified against backtest engine (0% drift).
