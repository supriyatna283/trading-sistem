# Trading Intelligence Platform

Professional Web-Based Trading Decision Support System.

> **⚠️ This system does NOT execute trades.** It provides analysis, insights, and decision support for manual traders.

## Architecture

- **Backend**: Python FastAPI with 8 core analysis engines
- **Frontend**: Next.js + React + TailwindCSS with TradingView charts
- **Database**: MySQL
- **Cache**: Redis
- **Real-time**: WebSocket

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- MySQL (Laragon)

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your DB credentials
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Docker (Alternative)
```bash
docker-compose up -d
```

## Core Modules

| Module | Description |
|--------|-------------|
| Market Data Engine | OHLCV from OKX/Bybit with caching |
| Market Structure | HH/HL/LH/LL, BOS, CHOCH detection |
| Smart Money Concepts | Order Blocks, FVG, Liquidity |
| Confluence Engine | Multi-TF scoring (0-8) |
| Setup Generator | Entry/SL/TP with R:R |
| Risk Management | Position sizing, daily limits |
| Market Scanner | Multi-asset scanning |
| Trading Journal | Win rate, PF, drawdown analytics |
| Alert System | Telegram, Email, Web push |

## API Docs

With backend running, visit: `http://localhost:8000/docs`

## Dashboard

Frontend at: `http://localhost:3000`
