---
title: Trading Intelligence API
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# Trading Intelligence Platform

Professional web-based trading **decision support** system with Smart Money Concepts, multi-timeframe analysis, risk management, and optional auto-trading.

## Important

| Mode | Default | Notes |
|------|---------|-------|
| **Analysis & signals** | Always on | Scanner, setups, charts, journal |
| **Auto-trading** | **OFF** (`enabled: false`) | Optional; uses Binance Futures API |
| **Dry-run** | **ON** (`dry_run: true`) | Logs orders without sending when auto-trading is enabled |

> Manual trading is the primary workflow. Auto-trading requires explicit configuration, Binance API keys, and `API_KEY` for protected endpoints.

## Data sources

| Exchange | Used for |
|----------|----------|
| **OKX** | Primary OHLCV, Smart Tape backend, tickers WebSocket |
| **Bybit** | Supplementary market data |
| **Binance** | Optional execution (auto-trading), Smart Tape browser feed |

Hyperliquid is **not** integrated yet.

## Architecture

- **Backend**: Python FastAPI
- **Frontend**: Next.js 16 + React 19 + Tailwind CSS 4
- **Database**: MySQL / TiDB
- **Cache**: Redis (optional)
- **Alerts**: WebSocket, Telegram, Email (SMTP)

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+
- MySQL (e.g. Laragon)

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set DB_*, optionally API_KEY and Telegram
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Set NEXT_PUBLIC_API_URL and NEXT_PUBLIC_API_KEY (same as backend API_KEY)
npm run dev
```

Open **http://localhost:3000** — API docs at **http://localhost:8000/docs**.

### Docker

```bash
docker-compose up -d
```

Set `API_KEY` in `docker-compose.yml` for both backend and frontend (`NEXT_PUBLIC_API_KEY`).

## Security

Protected endpoints (require header `X-API-Key` when `API_KEY` is set on the server):

- Trading: config, execute, close
- Setups: delete, clear, status updates, bulk generate
- Risk: update settings
- Alerts: test, update settings
- Scheduler: manual trigger

In **development**, if `API_KEY` is empty, writes are allowed (with a startup warning). In **production**, an unset `API_KEY` blocks writes with HTTP 503.

## Core modules

| Module | Description |
|--------|-------------|
| Market Data | OHLCV from OKX/Bybit |
| Market Structure | HH/HL/LH/LL, BOS, CHOCH |
| Smart Money | Order blocks, FVG, liquidity |
| Confluence | Multi-TF scoring |
| Setup Generator | Entry / SL / TP with R:R |
| Risk Management | Position sizing, daily limits |
| Scanner | Multi-asset scan |
| Journal | Win rate, profit factor, drawdown |
| Alerts | Telegram, email (SMTP), web |
| Auto-trading | Optional Binance Futures (dry-run default) |

## Environment variables

See `backend/.env.example` and `frontend/.env.example`.
