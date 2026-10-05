# Multi-Exchange Futures Bot — RSI-2 Mean Reversion + EMA (v2)

Ek complete Python-based crypto futures trading bot with web UI.
**Supported Exchanges: Binance USDT-M, WEEX, MEXC** (sab futures/perpetual).

## Strategy (v2 default): RSI-2 Mean Reversion + 200-SMA Filter

Yeh duniya ka sab se zyada backtested high-win-rate strategy family hai
(Larry Connors ke RSI-2 par based, crypto ke liye adapt kiya gaya).

| Indicator | Period | Kaam |
|-----------|--------|------|
| RSI       | 2      | Entry/exit trigger (extreme oversold/overbought) |
| SMA       | 200    | Long-term trend filter |
| EMA       | 8/13/21/55 | Chart display (legacy mode ke liye signals) |

### Rules — RSI-2 Mode (default, `strategy: "rsi2"`)
- **LONG (BUY)**: Price SMA-200 ke **UPAR** ho (uptrend) AUR RSI(2) fresh taur pe **10 se neeche** gir jaye (extreme dip).
- **SHORT (SELL)**: Price SMA-200 ke **NEECHE** ho (downtrend) AUR RSI(2) fresh taur pe **90 se upar** jaye (extreme rip).
- **Exit LONG**: RSI(2) **65 se upar** recover ho jaye (mean reversion complete) YA hard SL hit ho.
- **Exit SHORT**: RSI(2) **35 se neeche** gir jaye YA hard SL hit ho.
- **SL**: Price-based (default 2% price move) — dono exchange aur software watchdog pe.
- **Recommended Timeframe**: 1h (default), 4h bhi accha. 5m avoid karein (noise + fees).

### Rules — Legacy EMA Mode (`strategy: "ema"`)
- **LONG (BUY)**: EMA 55 baaki EMAs (8, 13, 21) se sabse **neeche** (fresh cross).
- **SHORT (SELL)**: EMA 55 sab se **upar** (fresh cross).
- **TP Modes**: Dynamic Trailing (TP1 1:1 -> BE SL -> trail) ya EMA55-reversal.

## Safe Defaults (v2 se)

| Setting | Purani default | Nayi default | Wajah |
|---------|---------------|--------------|-------|
| Leverage | 125x | **10x** | 125x pe fees (~15% margin/round-trip) + 0.64% SL noise se account khatam |
| Timeframe | 5m | **1h** | 5m EMA cross whipsaw machine hai; 1h pe signals reliable |
| TP | Trailing-only | **RSI-exit** (mean reversion) | TP1 ke baad profit book hota hai, breakeven trap nahi |

Leverage ab bhi UI se 125x tak set kar sakte hain, lekin **5-10x recommended**.

## Features

- Web UI (http://localhost:5000) - mobile + desktop responsive
- **3 exchanges: Binance + WEEX + MEXC** (config se select karein)
- **2 strategies: RSI-2 Mean Reversion (default) + EMA crossover** (UI se switch)
- Testnet (Binance/WEEX) + Mainnet support (MEXC sirf mainnet — MEXC ka public demo nahi hai)
- Real-time price chart with 4 EMA overlays + RSI/SMA indicator panel
- Live position, PnL, balance display
- Activity logs (real-time), manual position close
- Long only / Short only / Both modes
- Auto-save configuration, Telegram/Email/WhatsApp alerts
- Backtest tool: `tools/backtest_rsi2.py` (real historical candles + fees ke saath)

---

## Installation (5 Steps)

### Step 1: Python Install Karein
Python 3.9+ chahiye. Download from https://python.org

Check karein:
```bash
python --version
```

### Step 2: Project Folder Mein Jaayein
```bash
cd binance-futures-bot
```

### Step 3: Virtual Environment Banaayein (recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / Mac
python3 -m venv venv
source venv/bin/activate
```

### Step 4: Dependencies Install Karein
```bash
pip install -r requirements.txt
```

### Step 5: Bot Start Karein
```bash
# Windows
run.bat

# Linux / Mac
chmod +x run.sh
./run.sh
```

Browser mein khol: **http://localhost:5000**

---

## Binance API Keys Kaise Lein

### Testnet (Recommended for testing - FREE)
1. Jaayein: https://testnet.binancefuture.com
2. Login karein (Binance account se)
3. Top right pe "API Key" button click karein
4. API Key aur Secret copy karein
5. Bot UI mein paste karein, Testnet select karein

### Mainnet (Real money - careful!)
1. Jaayein: https://www.binance.com
2. Account -> API Management
3. "Create API" click karein
4. **Permissions**: Enable Futures, Disable Withdrawals
5. IP restriction ON karein (recommended)
6. API Key + Secret copy karein
7. Bot UI mein paste karein, Mainnet select karein

---

## UI Usage

1. **Settings panel** mein API Key, Secret, Symbol, Timeframe, Leverage, Amount daalein.
2. **Save** button dabayein.
3. **START BOT** dabayein - bot ab background mein strategy run karega.
4. **Activity Logs** mein har action dikhega.
5. **Live Indicators** panel mein EMAs aur current signal dikhega.
6. **Open Position** panel mein current position aur PnL dikhega.
7. STOP BOT dabane se bot ruk jaayega (position close nahi hoti).
8. **Close Position** button se manual close kar sakte hain.

---

## Configuration Options

| Field      | Default  | Description                                  |
|------------|----------|----------------------------------------------|
| api_key    | (empty)  | Binance Futures API key                      |
| api_secret | (empty)  | Binance Futures API secret                   |
| testnet    | true     | Testnet (safe) ya Mainnet (real money)       |
| symbol     | BTCUSDT  | Trading pair                                 |
| timeframe  | 1d       | 1m, 5m, 15m, 1h, 4h, 1d, 1w                 |
| leverage   | 10       | 1-125x                                       |
| amount     | 100      | USDT position size                           |
| mode       | both     | long / short / both                          |

---

## Project Structure

```
binance-futures-bot/
├── app.py                  # Flask web app (main entry point)
├── requirements.txt        # Python dependencies
├── config.json             # Auto-saved user configuration
├── run.sh / run.bat        # Quick start scripts
├── bot/                    # Trading logic package
│   ├── __init__.py
│   ├── indicators.py       # EMA, SMA, RSI, ATR calculations
│   ├── strategy.py         # Quad EMA crossover strategy
│   ├── trader.py           # Binance Futures API wrapper
│   └── engine.py           # Background trading engine
├── templates/
│   └── dashboard.html      # Web UI
├── static/
│   ├── css/style.css       # Dark trading theme
│   └── js/app.js           # Frontend logic (Socket.IO + chart)
├── logs/                   # Bot logs (auto-created)
└── README.md
```

---

## Strategy Logic (Code Reference)

```python
# BUY signal: EMA55 is the LOWEST of all four EMAs
if e55 < e8 and e55 < e13 and e55 < e21:
    signal = BUY   # go LONG

# SELL signal: EMA55 is the HIGHEST of all four EMAs
elif e55 > e8 and e55 > e13 and e55 > e21:
    signal = SELL  # go SHORT

else:
    signal = HOLD  # no action
```

---

## Troubleshooting

**Q: Bot start nahi ho raha?**
- API key/secret sahi daalein.
- Testnet pe account banayein: https://testnet.binancefuture.com
- Internet connection check karein.

**Q: "Insufficient margin" error?**
- Amount kam karein ya leverage badhaayein.
- Testnet pe balance recharge karein.

**Q: "Leverage not changed" error?**
- Yeh normal hai - Binance bolta hai leverage pehle se same hai. Ignore karein.

**Q: Chart update nahi ho raha?**
- Bot running ho, fir 30 second wait karein.

**Q: Python package install error?**
- `pip install --upgrade pip` chalayein.
- Python 3.9+ zaroori hai.

---

## Safety Warnings

- **Pehle TESTNET par test karein** - kabhi bhi real paise se shuru mat karein.
- Yeh bot educational purpose ke liye hai. Trading mein loss ka risk hai.
- Always start with small amounts.
- Bot ko chhod kar mat jaayein jab real money use kar rahe ho.
- Author kisi bhi loss ka zimmedaar nahi hai.

---

## License

MIT - Free to use, modify, distribute.

---

## Support

Issues ya questions ke liye logs/ folder mein `bot.log` check karein.
