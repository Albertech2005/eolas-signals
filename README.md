# ⚡ EOLAS Signal Engine

A production-ready perpetual trading signal platform that uses real-time data from Binance, Bybit, OKX, and Coinglass to generate high-confidence LONG/SHORT signals mapped directly to [EOLAS Perps DEX](https://perps.eolas.fun).

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Data Layer        │  Signal Engine    │  Delivery       │
│  ─────────────     │  ─────────────    │  ─────────      │
│  Binance Futures   │  OI Divergence    │  Web Dashboard  │
│  Bybit V5          │  Funding Rate     │  REST API       │
│  OKX Swaps         │  Liquidation      │  WebSocket      │
│  Coinglass         │  Momentum         │  Telegram Alerts│
│  (liquidations)    │  Volatility Gate  │  EOLAS Trade CTA│
└─────────────────────────────────────────────────────────┘
         ↓                   ↓                   ↓
    PostgreSQL            Redis Cache         Next.js UI
```

## Signal Scoring (0-100)

| Module              | Max Score | Signal Condition                         |
|---------------------|-----------|------------------------------------------|
| OI Divergence       | 25        | OI rising while price flat → LONG        |
| Funding Rate        | 20        | Extreme +/- funding → mean reversion     |
| Liquidation Pressure| 25        | Asymmetric liquidations → cascade predict|
| Momentum            | 20        | Strong move + elevated volume + RSI      |
| Volatility Quality  | 10        | ATR-based trending conditions gate       |

**Signal fires only when:**
- Total score ≥ 70
- At least 2 "strong" module signals agree on direction
- Volatility score ≥ 3 (not too choppy)
- No signal within last 15 minutes for same asset

---

## Prerequisites

- **Docker + Docker Compose** (recommended path)
- OR: Python 3.12+, Node 20+, PostgreSQL 15+, Redis 7+

---

## Quick Start (Docker — recommended)

### 1. Clone / enter the project

```bash
cd eolas-signals
```

### 2. Configure environment

```bash
cp .env.example .env
nano .env   # or vim, or your editor of choice
```

**Minimum required:**
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHANNEL_ID` (for alerts)
- Everything else works out-of-the-box with defaults

### 3. Launch

```bash
docker compose up -d
```

That's it. Services start in order: Postgres → Redis → Backend → Frontend.

### 4. Open dashboard

```
http://localhost:3000
```

Backend API docs:
```
http://localhost:8000/docs
```

---

## Manual Setup (without Docker)

### Backend

```bash
cd backend

# Create venv
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install deps
pip install -r requirements.txt

# Set up env
cp ../.env.example .env
# Edit .env — set DATABASE_URL to your local postgres, REDIS_URL to your redis

# Start
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
cp ../.env.example .env.local
# Edit .env.local for frontend vars (NEXT_PUBLIC_*)
npm run dev
```

---

## Telegram Bot Setup

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow prompts
2. Copy the token → paste into `.env` as `TELEGRAM_BOT_TOKEN`
3. Create a Telegram channel (public or private)
4. Add your bot as an **administrator** of the channel
5. Set `TELEGRAM_CHANNEL_ID` to `@yourchannelname` or the numeric ID (`-100xxxxxxxxxx`)

Test with:
```bash
curl http://localhost:8000/api/signals/live
```
A signal above 70 confidence will trigger a Telegram message.

---

## Supported Markets

| Symbol | EOLAS Market  |
|--------|--------------|
| BTC    | BTC-PERP     |
| ETH    | ETH-PERP     |
| SOL    | SOL-PERP     |
| BNB    | BNB-PERP     |
| ARB    | ARB-PERP     |
| OP     | OP-PERP      |

Add more in `backend/app/config.py` — `SUPPORTED_SYMBOLS` and `EOLAS_MARKET_MAP`.

---

## API Reference

| Endpoint                    | Description                              |
|-----------------------------|------------------------------------------|
| `GET /api/signals/live`     | Real-time engine evaluation (all markets)|
| `GET /api/signals/active`   | Active signals from DB (cached)          |
| `GET /api/signals/latest`   | Latest N signals                         |
| `GET /api/markets`          | All market data with EOLAS trade links   |
| `GET /api/markets/{symbol}` | Single market data                       |
| `GET /api/analytics/performance` | Win rate + PnL stats               |
| `GET /api/analytics/leaderboard` | Symbol leaderboard by win rate     |
| `GET /api/analytics/stats/summary` | Dashboard summary numbers        |
| `WS  /ws`                   | Live WebSocket signal stream             |
| `GET /api/health`           | Health check + data freshness            |

---

## EOLAS DEX Integration

Trade links are auto-generated per signal. Format:

```
https://perps.eolas.fun/trade/{SYMBOL}-PERP?side=long|short
```

Update `EOLAS_BASE_URL` and `EOLAS_TRADE_PATH` in `.env` or `config.py`
if the EOLAS URL structure differs.

---

## Production Deployment (VPS)

```bash
# 1. Pull to server
git clone ... && cd eolas-signals

# 2. Configure
cp .env.example .env && nano .env
# Set CORS_ORIGINS to your actual domain
# Set NEXT_PUBLIC_API_URL to your backend URL

# 3. Deploy
docker compose -f docker-compose.yml up -d --build

# 4. Set up reverse proxy (nginx example)
# server {
#   server_name signals.yourdomain.com;
#   location / { proxy_pass http://localhost:3000; }
# }
# server {
#   server_name api.signals.yourdomain.com;
#   location / { proxy_pass http://localhost:8000; }
# }
```

---

## Tuning the Signal Engine

Edit `backend/app/config.py`:

```python
MIN_CONFIDENCE_SCORE = 70     # Raise to 75-80 for fewer, higher-quality signals
SIGNAL_COOLDOWN_MINUTES = 15  # Raise to reduce frequency
DEFAULT_SL_PCT = 0.02         # Adjust risk/reward
```

Edit individual module files in `backend/app/signals/modules/` to adjust
scoring thresholds per-module.

---

## ⚠️ Disclaimer

This software generates trading signal ideas based on technical market data.
It does **not** guarantee profits. Cryptocurrency trading involves significant
risk of loss. Always use your own judgment and risk management.
Not financial advice.
