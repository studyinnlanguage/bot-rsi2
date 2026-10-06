# DEPLOY & SALE PLAYBOOK (v2.1)

Tumhare liye step-by-step: VPS setup → pehla client → scaling. Roman Urdu
main, practical.

## Part 1 — VPS Deploy (30 minute)

### 1. VPS kharido
- Contabo / Hetzner / DigitalOcean — **2GB RAM, 1 CPU** start ke liye kaafi
  (10 users tak). Ubuntu 22/24.
- Budget: $6-10/month. 50 users tak 4GB/2CPU ($15/month).

### 2. One-command install
```bash
ssh root@YOUR_SERVER_IP
apt update && apt install -y unzip
# repo upload (github se ya zip):
git clone https://github.com/studyinnlanguage/bot-rsi2.git
cd bot-rsi2 && chmod +x install.sh && ./install.sh
```

### 3. Public URL (FREE)
```bash
cloudflared tunnel --url http://localhost:5000
```
Jo URL mile (`https://xxx.trycloudflare.com`) wahi tumhara sales URL hai.
Permanent domain chahiye to Cloudflare free account se named tunnel banao
(DEPLOY_NOTES me detail).

### 4. Admin setup
- `/admin` → password: `.env` ka `ADMIN_SECRET` (install script generate
  karta hai — **use change karo**)
- Test: khud ek test account banao, testnet pe bot start karke dekho

## Part 2 — Pehla Client (Sales Script)

### Step 1: Expectation set karo (HONEST pitch — ye tumhari strength hai)
> "Ye bot Larry Connors ki RSI-2 strategy use karta hai — 30+ saal se
> documented. 2023-2026 real data par verified: 67-70% win rate.
> Koi 90% win-rate wala bot sach nahi hota — wo screenshots edit karte hain.
> Is bot ka har number backtest report me hai jo tum khud chala sakte ho."

Trust = sales. Evidence folder dikhao (`BACKTEST_RESULTS.md`).

### Step 2: Setup karo client ke sath (screen share)
1. Sign up (trial auto 7-day)
2. **Exchange: MEXC** (fees 0.00/0.01% — verified numbers isi par) ya Binance
3. API keys: futures key, **withdrawals OFF** (sirf trade permission)
4. Coins: **BTC + ETH** (PRO preset)
5. **PRO preset button click** → SL 5% auto, 4h auto, 10x auto
6. Testnet pe 2-3 din chalao → phir mainnet small amount

### Step 3: Rules jo client ko BOL do (liability protection)
- Leverage 10x se upar mat karo (20x+ popup warning hai)
- Meme coins mat chalana (LINK/TRX/XRP/BNB bhi nahi — verified losers)
- Bot ko 24/7 chalne do, panic me band mat karo
- Ye investment advice nahi hai

## Part 3 — Pricing & Positioning

| Plan | Price | Kise |
|---|---|---|
| Trial | FREE 7d | sab (testnet pe) |
| Monthly | $30-40 | casual |
| Quarterly | $75-100 | serious |
| Yearly | $250-300 | committed |
| Lifetime | $400-500 | early birds (limited) |

**Upsell ideas:**
- "Setup + 1h training call" — $25 one-time
- "Custom coins/presets" — $15
- Referral: client ko 1 month free per paid referral (system built-in hai)

## Part 4 — Support Checklist (per client)

- [ ] Trial user bana, testnet verify
- [ ] Subscription plan set (admin panel Extend)
- [ ] Telegram alerts connect (bot config me token)
- [ ] Weekly check: `pm2 status`, logs, server uptime
- [ ] Database backup: `cp database.json backup-$(date +%F).json`

## Part 5 — Legal/Cover-yourself

- Terms me likho: "Software tool only. No profit guarantee. Trading risk
  borne by user." (payment page pe disclaimer already hai — padh lo)
- Refund policy decide karo (7-day trial hi tumhara filter hai)
- Profit screenshots apne test se banao, doosron ke chhapaao mat

## Common Client Questions (FAQ)

**Q: Profit guarantee hai?**
A: Nahi. Verified 67-70% win rate hai, drawdowns aate hain. Jo guarantee
deta hai us se door raho.

**Q: Mera paisa bot ke paas rehta hai?**
A: Nahi — bot sirf API trade permission use karta hai, withdrawal nahi.
Paisa exchange pe tumhara hi rehta hai.

**Q: 50x laga loon?**
A: 50x par 2% move = liquidation. Humne real data se dikhaya hai ke meme
coin pe 50x = 14 din me 17 liquidations. 10x raho.

**Q: Daily kitna milega?**
A: Fixed daily return kisi nahi deta. Average ~120%/year on margin @10x
(verified 2023-26), magar months me loss bhi aayega.

**Q: Meme coin pe chalega?**
A: Backtest me har config pe loss aaya. BTC/ETH hi recommended.
