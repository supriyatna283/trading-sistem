"""
Order Flow Router — Footprint & Smart Tape Endpoints
=====================================================
REST endpoints for footprint data and whale detection.
WebSocket endpoint for real-time Smart Tape feed.

/whale-intel/{symbol}  — Powerful multi-signal whale position detector.
"""

import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.engines.order_flow_engine import order_flow_engine, WHALE_THRESHOLD_USDT, FISH_THRESHOLD_USDT
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/orderflow", tags=["Order Flow"])

# ─────────────────────────────────────────────────────────────────
# Shared HTTP client (reused per request module)
# ─────────────────────────────────────────────────────────────────
_http = httpx.AsyncClient(
    timeout=8.0, verify=False,
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
)

FUTURES_BASE = "https://fapi.binance.com"
SPOT_BASE    = "https://api.binance.com"


# ─────────────────────────────────────────────────────────────────
# Helper: fetch aggTrades (Futures first → Spot fallback)
# ─────────────────────────────────────────────────────────────────
async def _fetch_agg_trades(symbol: str, limit: int = 1000) -> list:
    for url in [
        f"{FUTURES_BASE}/fapi/v1/aggTrades",
        f"{SPOT_BASE}/api/v3/aggTrades",
    ]:
        try:
            r = await _http.get(url, params={"symbol": symbol.upper(), "limit": limit})
            if r.status_code == 200:
                data = r.json()
                if data:
                    return data
        except Exception as e:
            logger.debug(f"aggTrades {url} error: {e}")
    return []


# ─────────────────────────────────────────────────────────────────
# Helper: fetch funding rate (Futures only, graceful fallback)
# ─────────────────────────────────────────────────────────────────
async def _fetch_funding(symbol: str) -> dict:
    try:
        r = await _http.get(f"{FUTURES_BASE}/fapi/v1/premiumIndex", params={"symbol": symbol.upper()})
        if r.status_code == 200:
            d = r.json()
            return {
                "funding_rate": float(d.get("lastFundingRate", 0)),
                "mark_price": float(d.get("markPrice", 0)),
                "next_funding_time": int(d.get("nextFundingTime", 0)),
            }
    except Exception:
        pass
    return {"funding_rate": 0.0, "mark_price": 0.0, "next_funding_time": 0}


# ─────────────────────────────────────────────────────────────────
# Helper: fetch Long/Short ratio (Futures only)
# ─────────────────────────────────────────────────────────────────
async def _fetch_ls_ratio(symbol: str) -> dict:
    try:
        r = await _http.get(
            f"{FUTURES_BASE}/futures/data/globalLongShortAccountRatio",
            params={"symbol": symbol.upper(), "period": "1h", "limit": 3},
        )
        if r.status_code == 200:
            data = r.json()
            if data:
                latest = data[0]
                ratio = float(latest.get("longShortRatio", 1.0))
                long_pct = float(latest.get("longAccount", 0.5)) * 100
                short_pct = float(latest.get("shortAccount", 0.5)) * 100
                # Trend: compare last 3 periods
                if len(data) >= 3:
                    older_ratio = float(data[-1].get("longShortRatio", ratio))
                    trend = "rising" if ratio > older_ratio else "falling" if ratio < older_ratio else "stable"
                else:
                    trend = "stable"
                return {
                    "ratio": round(ratio, 3),
                    "long_pct": round(long_pct, 1),
                    "short_pct": round(short_pct, 1),
                    "trend": trend,
                    "available": True,
                }
    except Exception:
        pass
    return {"ratio": None, "long_pct": None, "short_pct": None, "trend": None, "available": False}


# ─────────────────────────────────────────────────────────────────
# Helper: fetch Open Interest
# ─────────────────────────────────────────────────────────────────
async def _fetch_open_interest(symbol: str) -> dict:
    try:
        r = await _http.get(f"{FUTURES_BASE}/fapi/v1/openInterest", params={"symbol": symbol.upper()})
        if r.status_code == 200:
            d = r.json()
            return {"open_interest": float(d.get("openInterest", 0)), "available": True}
    except Exception:
        pass
    return {"open_interest": 0.0, "available": False}


# ─────────────────────────────────────────────────────────────────
# MAIN: Powerful Whale Intel endpoint
# ─────────────────────────────────────────────────────────────────
@router.get("/whale-intel/{symbol}")
async def get_whale_intel(symbol: str):
    """
    Powerful multi-signal whale position detector.

    Aggregates 4 data sources from Binance:
    1. AggTrades (last 1000 trades) — buy/sell pressure & whale/shark count
    2. Long/Short Ratio — do whales lean LONG or SHORT?
    3. Funding Rate — positive = longs paying (over-leveraged longs)
    4. Open Interest — total open contracts (rising OI + buy delta = strong)

    Returns a DOMINANT_POSITION (LONG / SHORT / NEUTRAL) with confidence score.
    """
    sym = symbol.upper()

    # ── 1. Fetch all 4 signals in parallel ──
    trades_raw, funding, ls_ratio, oi = await asyncio.gather(
        _fetch_agg_trades(sym, limit=1000),
        _fetch_funding(sym),
        _fetch_ls_ratio(sym),
        _fetch_open_interest(sym),
        return_exceptions=True,
    )
    if isinstance(trades_raw, Exception): trades_raw = []
    if isinstance(funding, Exception): funding = {"funding_rate": 0.0, "mark_price": 0.0}
    if isinstance(ls_ratio, Exception): ls_ratio = {"available": False}
    if isinstance(oi, Exception): oi = {"available": False}

    # ── 2. Process AggTrades ──
    buy_vol = sell_vol = buy_usd = sell_usd = 0.0
    whale_buys = whale_sells = []
    shark_buys = shark_sells = []
    WHALE_USD = 50_000
    SHARK_USD = 10_000

    for t in trades_raw:
        try:
            price = float(t["p"])
            qty   = float(t["q"])
            notional = price * qty
            is_sell = t["m"]  # maker = sell aggressor

            if is_sell:
                sell_vol += qty
                sell_usd += notional
                if notional >= WHALE_USD:
                    whale_sells.append({"notional": round(notional, 0), "price": price, "qty": qty})
                elif notional >= SHARK_USD:
                    shark_sells.append({"notional": round(notional, 0), "price": price, "qty": qty})
            else:
                buy_vol += qty
                buy_usd += notional
                if notional >= WHALE_USD:
                    whale_buys.append({"notional": round(notional, 0), "price": price, "qty": qty})
                elif notional >= SHARK_USD:
                    shark_buys.append({"notional": round(notional, 0), "price": price, "qty": qty})
        except Exception:
            continue

    total_vol = buy_vol + sell_vol
    buy_pct   = round(buy_vol / total_vol * 100, 1) if total_vol > 0 else 50.0
    sell_pct  = round(100 - buy_pct, 1)
    delta_usd = round(buy_usd - sell_usd, 0)
    whale_delta = len(whale_buys) - len(whale_sells)
    shark_delta = len(shark_buys) - len(shark_sells)

    # ── 3. Score each signal (LONG = positive, SHORT = negative) ──
    # Each signal contributes -2 to +2 points
    score = 0
    signals = []

    # Signal A: AggTrades pressure
    if buy_pct > 60:
        score += 2
        signals.append({"key": "agg_trades", "label": "Order Flow", "value": f"BUY {buy_pct}%", "direction": "LONG", "weight": 2})
    elif buy_pct > 54:
        score += 1
        signals.append({"key": "agg_trades", "label": "Order Flow", "value": f"BUY {buy_pct}%", "direction": "LONG", "weight": 1})
    elif sell_pct > 60:
        score -= 2
        signals.append({"key": "agg_trades", "label": "Order Flow", "value": f"SELL {sell_pct}%", "direction": "SHORT", "weight": 2})
    elif sell_pct > 54:
        score -= 1
        signals.append({"key": "agg_trades", "label": "Order Flow", "value": f"SELL {sell_pct}%", "direction": "SHORT", "weight": 1})
    else:
        signals.append({"key": "agg_trades", "label": "Order Flow", "value": f"NEUTRAL {buy_pct}%/{sell_pct}%", "direction": "NEUTRAL", "weight": 0})

    # Signal B: Whale net delta
    if whale_delta > 2:
        score += 2
        signals.append({"key": "whale_delta", "label": "Whale Net", "value": f"+{whale_delta} buys", "direction": "LONG", "weight": 2})
    elif whale_delta > 0:
        score += 1
        signals.append({"key": "whale_delta", "label": "Whale Net", "value": f"+{whale_delta} buy", "direction": "LONG", "weight": 1})
    elif whale_delta < -2:
        score -= 2
        signals.append({"key": "whale_delta", "label": "Whale Net", "value": f"{whale_delta} sells", "direction": "SHORT", "weight": 2})
    elif whale_delta < 0:
        score -= 1
        signals.append({"key": "whale_delta", "label": "Whale Net", "value": f"{whale_delta} sell", "direction": "SHORT", "weight": 1})
    else:
        signals.append({"key": "whale_delta", "label": "Whale Net", "value": "0 (no activity)", "direction": "NEUTRAL", "weight": 0})

    # Signal C: Long/Short Ratio
    if ls_ratio.get("available"):
        ratio = ls_ratio["ratio"]
        if ratio and ratio > 1.5:
            # Many longs = contrarian SHORT signal (crowded longs = squeeze risk)
            score -= 1
            signals.append({"key": "ls_ratio", "label": "L/S Ratio", "value": f"{ratio} (longs crowded)", "direction": "SHORT", "weight": 1})
        elif ratio and ratio < 0.7:
            # Many shorts = contrarian LONG signal
            score += 1
            signals.append({"key": "ls_ratio", "label": "L/S Ratio", "value": f"{ratio} (shorts crowded)", "direction": "LONG", "weight": 1})
        elif ratio and 0.9 <= ratio <= 1.1:
            signals.append({"key": "ls_ratio", "label": "L/S Ratio", "value": f"{ratio} (balanced)", "direction": "NEUTRAL", "weight": 0})
        else:
            dir_ = "LONG" if ratio and ratio >= 1.1 else "SHORT"
            signals.append({"key": "ls_ratio", "label": "L/S Ratio", "value": str(ratio), "direction": dir_, "weight": 0})
    else:
        signals.append({"key": "ls_ratio", "label": "L/S Ratio", "value": "Futures only (N/A for spot)", "direction": "NEUTRAL", "weight": 0})

    # Signal D: Funding Rate
    fr = funding.get("funding_rate", 0.0)
    if fr > 0.001:
        # Very positive funding = longs paying heavily = squeeze risk = SHORT signal
        score -= 1
        signals.append({"key": "funding", "label": "Funding Rate", "value": f"+{fr*100:.4f}% (long squeeze risk)", "direction": "SHORT", "weight": 1})
    elif fr > 0.0003:
        signals.append({"key": "funding", "label": "Funding Rate", "value": f"+{fr*100:.4f}% (longs paying)", "direction": "NEUTRAL", "weight": 0})
    elif fr < -0.001:
        # Very negative funding = shorts paying heavily = long squeeze risk
        score += 1
        signals.append({"key": "funding", "label": "Funding Rate", "value": f"{fr*100:.4f}% (short squeeze risk)", "direction": "LONG", "weight": 1})
    else:
        signals.append({"key": "funding", "label": "Funding Rate", "value": f"{fr*100:.4f}% (neutral)", "direction": "NEUTRAL", "weight": 0})

    # ── 4. Determine dominant position ──
    max_possible = 8  # 2+2+1+1 per side
    confidence_pct = round(abs(score) / max_possible * 100, 0)

    if score >= 4:
        dominant_position = "STRONG LONG"
        dom_color = "bullish"
    elif score >= 2:
        dominant_position = "LONG"
        dom_color = "bullish"
    elif score <= -4:
        dominant_position = "STRONG SHORT"
        dom_color = "bearish"
    elif score <= -2:
        dominant_position = "SHORT"
        dom_color = "bearish"
    else:
        dominant_position = "NEUTRAL"
        dom_color = "neutral"

    # ── 5. Build summary narrative ──
    long_signals  = [s for s in signals if s["direction"] == "LONG"]
    short_signals = [s for s in signals if s["direction"] == "SHORT"]

    return {
        "symbol": sym,
        "dominant_position": dominant_position,
        "dom_color": dom_color,
        "score": score,
        "max_score": max_possible,
        "confidence_pct": int(confidence_pct),
        "signals": signals,
        "long_signal_count": len(long_signals),
        "short_signal_count": len(short_signals),
        # AggTrades raw
        "order_flow": {
            "buy_pct": buy_pct,
            "sell_pct": sell_pct,
            "delta_usd": delta_usd,
            "total_trades": len(trades_raw),
            "whale_buy_count": len(whale_buys),
            "whale_sell_count": len(whale_sells),
            "shark_buy_count": len(shark_buys),
            "shark_sell_count": len(shark_sells),
            "top_whale_buys": sorted(whale_buys, key=lambda x: x["notional"], reverse=True)[:3],
            "top_whale_sells": sorted(whale_sells, key=lambda x: x["notional"], reverse=True)[:3],
        },
        # Supporting data
        "ls_ratio": ls_ratio,
        "funding_rate": fr,
        "mark_price": funding.get("mark_price", 0),
        "open_interest": oi.get("open_interest", 0) if isinstance(oi, dict) else 0,
        "data_sources": {
            "agg_trades": len(trades_raw) > 0,
            "ls_ratio": ls_ratio.get("available", False),
            "funding": fr != 0.0,
            "open_interest": oi.get("available", False) if isinstance(oi, dict) else False,
        }
    }


# ─── Footprint ───

@router.get("/footprint/{symbol}")
async def get_footprint(
    symbol: str,
    timeframe: str = Query("5m", description="Candle timeframe"),
    limit: int = Query(10, description="Number of candles", ge=1, le=50),
):
    """
    Get footprint candles for a symbol: buy/sell volume per price level,
    delta, Point of Control (POC), and cumulative delta.
    """
    candles = await order_flow_engine.get_footprint(symbol.upper(), timeframe, limit)
    flow_summary = {}
    if candles:
        all_deltas = [c["delta"] for c in candles]
        total_buy = sum(c["total_buy_vol"] for c in candles)
        total_sell = sum(c["total_sell_vol"] for c in candles)
        flow_summary = {
            "cumulative_delta": round(sum(all_deltas), 4),
            "total_buy_vol": round(total_buy, 4),
            "total_sell_vol": round(total_sell, 4),
            "dominance": "BUY" if total_buy > total_sell else "SELL",
        }
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "candles": candles,
        "flow_summary": flow_summary,
    }


# ─── Whale / Smart Tape ───

@router.get("/whales/{symbol}")
async def get_whales(
    symbol: str,
    threshold_usdt: float = Query(WHALE_THRESHOLD_USDT, description="Minimum notional value in USDT"),
    limit: int = Query(50, ge=1, le=200),
    lookback_seconds: int = Query(3600, description="Lookback window in seconds"),
):
    trades = await order_flow_engine.get_recent_whales(
        symbol.upper(), threshold_usdt, limit, lookback_seconds
    )
    summary = order_flow_engine.get_flow_summary(trades)
    return {
        "symbol": symbol.upper(),
        "threshold_usdt": threshold_usdt,
        "lookback_seconds": lookback_seconds,
        "trades": trades,
        "summary": summary,
        "whale_count": len([t for t in trades if t["tier"] == "WHALE"]),
        "shark_count": len([t for t in trades if t["tier"] == "SHARK"]),
    }


@router.get("/whales/scan/multi")
async def scan_multi_symbols(
    symbols: str = Query("BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"),
    threshold_usdt: float = Query(WHALE_THRESHOLD_USDT),
    lookback_seconds: int = Query(300),
):
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    trades = await order_flow_engine.get_multi_symbol_whales(sym_list, threshold_usdt, lookback_seconds)
    summary = order_flow_engine.get_flow_summary(trades)
    return {
        "symbols": sym_list,
        "threshold_usdt": threshold_usdt,
        "lookback_seconds": lookback_seconds,
        "trades": trades,
        "summary": summary,
    }


@router.get("/whales/live/cached")
async def get_cached_whales(symbol: Optional[str] = Query(None)):
    trades = order_flow_engine.get_cached_whales(symbol.upper() if symbol else None)
    summary = order_flow_engine.get_flow_summary(trades)
    return {"trades": trades, "summary": summary, "count": len(trades)}


# ─── Real-time WebSocket ───

@router.websocket("/ws/tape")
async def tape_websocket(websocket: WebSocket):
    from app.services.tape_ws_manager import smart_tape_manager
    await websocket.accept()
    logger.info("📡 Smart Tape WebSocket client connected")
    cached = order_flow_engine.get_cached_whales()
    if cached:
        import json
        await websocket.send_text(json.dumps({"type": "initial", "data": cached}))
    try:
        await smart_tape_manager.connect_client(websocket)
    except WebSocketDisconnect:
        logger.info("📴 Smart Tape WebSocket client disconnected")
    except Exception as e:
        logger.warning(f"Tape WS error: {e}")



# ─── Footprint ───

@router.get("/footprint/{symbol}")
async def get_footprint(
    symbol: str,
    timeframe: str = Query("5m", description="Candle timeframe"),
    limit: int = Query(10, description="Number of candles", ge=1, le=50),
):
    """
    Get footprint candles for a symbol: buy/sell volume per price level,
    delta, Point of Control (POC), and cumulative delta.
    """
    candles = await order_flow_engine.get_footprint(symbol.upper(), timeframe, limit)
    flow_summary = {}
    if candles:
        all_deltas = [c["delta"] for c in candles]
        total_buy = sum(c["total_buy_vol"] for c in candles)
        total_sell = sum(c["total_sell_vol"] for c in candles)
        flow_summary = {
            "cumulative_delta": round(sum(all_deltas), 4),
            "total_buy_vol": round(total_buy, 4),
            "total_sell_vol": round(total_sell, 4),
            "dominance": "BUY" if total_buy > total_sell else "SELL",
        }
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "candles": candles,
        "flow_summary": flow_summary,
    }


# ─── Whale / Smart Tape ───

@router.get("/whales/{symbol}")
async def get_whales(
    symbol: str,
    threshold_usdt: float = Query(WHALE_THRESHOLD_USDT, description="Minimum notional value in USDT"),
    limit: int = Query(50, ge=1, le=200),
    lookback_seconds: int = Query(3600, description="Lookback window in seconds"),
):
    """
    Fetch large trades (whale detection) for a single symbol.
    Returns sorted by notional value descending.
    """
    trades = await order_flow_engine.get_recent_whales(
        symbol.upper(), threshold_usdt, limit, lookback_seconds
    )
    summary = order_flow_engine.get_flow_summary(trades)
    return {
        "symbol": symbol.upper(),
        "threshold_usdt": threshold_usdt,
        "lookback_seconds": lookback_seconds,
        "trades": trades,
        "summary": summary,
        "whale_count": len([t for t in trades if t["tier"] == "WHALE"]),
        "shark_count": len([t for t in trades if t["tier"] == "SHARK"]),
    }


@router.get("/whales/scan/multi")
async def scan_multi_symbols(
    symbols: str = Query("BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT"),
    threshold_usdt: float = Query(WHALE_THRESHOLD_USDT),
    lookback_seconds: int = Query(300),
):
    """
    Scan multiple symbols for whale trades concurrently (default: last 5 minutes).
    """
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    trades = await order_flow_engine.get_multi_symbol_whales(sym_list, threshold_usdt, lookback_seconds)
    summary = order_flow_engine.get_flow_summary(trades)
    return {
        "symbols": sym_list,
        "threshold_usdt": threshold_usdt,
        "lookback_seconds": lookback_seconds,
        "trades": trades,
        "summary": summary,
    }


@router.get("/whales/live/cached")
async def get_cached_whales(symbol: Optional[str] = Query(None)):
    """
    Get cached whale trades collected from the real-time WebSocket stream.
    Optionally filter by symbol.
    """
    trades = order_flow_engine.get_cached_whales(symbol.upper() if symbol else None)
    summary = order_flow_engine.get_flow_summary(trades)
    return {"trades": trades, "summary": summary, "count": len(trades)}


# ─── Real-time WebSocket ───

@router.websocket("/ws/tape")
async def tape_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time Smart Tape feed.
    Streams whale/large trades as they occur across all monitored symbols.
    Connect at: ws://127.0.0.1:8000/api/v1/orderflow/ws/tape
    """
    from app.services.tape_ws_manager import smart_tape_manager
    await websocket.accept()
    logger.info("📡 Smart Tape WebSocket client connected")

    # Send initial cached trades
    cached = order_flow_engine.get_cached_whales()
    if cached:
        import json
        await websocket.send_text(json.dumps({"type": "initial", "data": cached}))

    try:
        await smart_tape_manager.connect_client(websocket)
    except WebSocketDisconnect:
        logger.info("📴 Smart Tape WebSocket client disconnected")
    except Exception as e:
        logger.warning(f"Tape WS error: {e}")
