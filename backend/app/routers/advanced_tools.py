"""
Advanced Trading Tools API — Sprint 3 + Sprint 4
==================================================
Endpoints:

SPRINT 3:
  POST /api/v1/advanced/mm-flow          — Market Maker Flow Tracker
  POST /api/v1/advanced/wyckoff          — Wyckoff Pattern Detector
  POST /api/v1/advanced/ml-score         — Adaptive ML Scoring
  POST /api/v1/advanced/portfolio        — Portfolio Optimizer
  POST /api/v1/advanced/full-analysis    — Sprint 3 combined analysis

SPRINT 4:
  POST /api/v1/advanced/garch            — GARCH Volatility Forecast
  POST /api/v1/advanced/options          — Options / Perps Analysis
  GET  /api/v1/advanced/signals          — Social Trading — Active Signals
  GET  /api/v1/advanced/leaderboard      — Social Trading — Leaderboard
  POST /api/v1/advanced/publish-signal   — Publish new signal
  POST /api/v1/advanced/copy-trade       — Calculate copy trade size
  GET  /api/v1/advanced/consensus/{sym}  — Consensus signal for symbol
"""

import logging
import numpy as np
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional, List

from app.engines.market_maker_flow import MarketMakerFlowEngine
from app.engines.wyckoff import WyckoffEngine
from app.engines.ml_scoring import AdaptiveMLScoringEngine
from app.engines.portfolio_optimizer import PortfolioOptimizerEngine
from app.engines.garch_volatility import GARCHVolatilityEngine
from app.engines.options_perps import OptionsPerpsEngine
from app.engines.social_trading import SocialTradingEngine
from app.engines.market_data import MarketDataEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/advanced", tags=["Advanced — Sprint 3 & 4"])

# Engine singletons
_mm_engine       = MarketMakerFlowEngine()
_wyckoff_engine  = WyckoffEngine()
_ml_engine       = AdaptiveMLScoringEngine()
_port_engine     = PortfolioOptimizerEngine()
_garch_engine    = GARCHVolatilityEngine()
_options_engine  = OptionsPerpsEngine()
_social_engine   = SocialTradingEngine()
_data_engine     = MarketDataEngine()


# ─────────────────────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────────────────────

class SymbolRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1h", example="1h")
    lookback: int = Field(100, ge=30, le=300)


class PortfolioRequest(BaseModel):
    symbols: List[str] = Field(..., example=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    timeframe: str = Field("1d", example="1d")
    lookback_days: int = Field(90, ge=30, le=365)
    current_weights: Optional[List[float]] = Field(None)


class GARCHRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1d", example="1d")
    lookback: int = Field(200, ge=60, le=500)


class OptionsRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    iv_30d_pct: float = Field(70.0, ge=1.0, le=500.0, description="30-day IV in %")
    funding_rate_8h: float = Field(0.01, description="8h funding rate in %")
    long_short_ratio: float = Field(1.0, ge=0.01, le=10.0)


class PublishSignalRequest(BaseModel):
    publisher_id: str = Field(..., example="pub_ict_trader")
    symbol: str = Field(..., example="BTCUSDT")
    direction: str = Field(..., example="BUY")
    entry: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    take_profits: List[float] = Field(default_factory=list)
    timeframe: str = Field("1h")
    rationale: str = Field("", max_length=500)
    tags: List[str] = Field(default_factory=list)


class CopyTradeRequest(BaseModel):
    signal_id: str = Field(..., example="SIG001")
    account_balance: float = Field(..., gt=0, example=10000)
    risk_pct: float = Field(1.0, ge=0.1, le=5.0)


class AdvancedFullAnalysisRequest(BaseModel):
    symbol: str = Field(..., example="BTCUSDT")
    timeframe: str = Field("1h")
    htf: str = Field("4h")
    iv_30d_pct: float = Field(70.0)
    funding_rate_8h: float = Field(0.01)


# ─────────────────────────────────────────────────────────────────────────────
# SPRINT 3 Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/mm-flow")
async def get_mm_flow(req: SymbolRequest):
    """Market Maker Flow analysis — CVD, delta, VWAP, MM phases, stop hunt prob."""
    try:
        df = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.lookback)
        if df is None or df.empty:
            return {"error": "No candle data", "symbol": req.symbol}
        result = _mm_engine.analyze(df)
        return {"symbol": req.symbol, "timeframe": req.timeframe, **_mm_engine.to_dict(result)}
    except Exception as e:
        logger.exception("MM Flow error")
        return {"error": str(e)}


@router.post("/wyckoff")
async def get_wyckoff(req: SymbolRequest):
    """Wyckoff Pattern Detection — accumulation/distribution schematics, phase."""
    try:
        df = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.lookback)
        if df is None or df.empty:
            return {"error": "No candle data", "symbol": req.symbol}
        result = _wyckoff_engine.analyze(df)
        return {"symbol": req.symbol, "timeframe": req.timeframe, **_wyckoff_engine.to_dict(result)}
    except Exception as e:
        logger.exception("Wyckoff error")
        return {"error": str(e)}


@router.post("/ml-score")
async def get_ml_score(req: SymbolRequest):
    """Adaptive ML Scoring — GBM with online learning, feature importance, regime."""
    try:
        df = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.lookback)
        if df is None or df.empty:
            return {"error": "No candle data", "symbol": req.symbol}
        result = _ml_engine.analyze(df)
        return {"symbol": req.symbol, "timeframe": req.timeframe, **_ml_engine.to_dict(result)}
    except Exception as e:
        logger.exception("ML score error")
        return {"error": str(e)}


@router.post("/portfolio")
async def get_portfolio_optimization(req: PortfolioRequest):
    """Portfolio optimization — Max Sharpe, Min Vol, Risk Parity, Monte Carlo."""
    try:
        # Fetch daily returns for each symbol
        returns_list = []
        valid_symbols = []

        for sym in req.symbols:
            df = await _data_engine.get_candles(sym, req.timeframe, limit=req.lookback_days + 10)
            if df is not None and not df.empty and len(df) >= 30:
                closes = df["close"].astype(float).values
                rets = np.diff(np.log(closes))
                returns_list.append(rets)
                valid_symbols.append(sym)

        if len(valid_symbols) < 2:
            return {"error": "Need at least 2 valid symbols with price data"}

        # Align length (min common length)
        min_len = min(len(r) for r in returns_list)
        returns_matrix = np.column_stack([r[-min_len:] for r in returns_list])

        result = _port_engine.optimize(valid_symbols, returns_matrix, req.current_weights)
        return {
            "symbols":   valid_symbols,
            "timeframe": req.timeframe,
            "lookback":  min_len,
            **_port_engine.to_dict(result),
        }
    except Exception as e:
        logger.exception("Portfolio opt error")
        return {"error": str(e)}


@router.post("/sprint3-analysis")
async def get_sprint3_combined(req: SymbolRequest):
    """Combined Sprint 3 analysis — MM Flow + Wyckoff + ML Score in one call."""
    try:
        df = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.lookback)
        if df is None or df.empty:
            return {"error": "No candle data", "symbol": req.symbol}

        mm     = _mm_engine.analyze(df)
        wyk    = _wyckoff_engine.analyze(df)
        ml     = _ml_engine.analyze(df)

        # Aggregate score
        total = mm.confluence_score + wyk.confluence_score + ml.confluence_score
        max_score = 15  # 5+5+5

        # Combined signal (majority vote)
        signals_map = {
            mm.flow_bias: 1, wyk.signal: 1, ml.signal: 1
        }
        bull_signals = sum(1 for s in [mm.flow_bias, wyk.signal, ml.signal]
                           if "BUY" in s)
        bear_signals = sum(1 for s in [mm.flow_bias, wyk.signal, ml.signal]
                           if "SELL" in s)

        if bull_signals >= 2:
            consensus = "BULLISH"
        elif bear_signals >= 2:
            consensus = "BEARISH"
        else:
            consensus = "NEUTRAL"

        return {
            "symbol":    req.symbol,
            "timeframe": req.timeframe,
            "consensus": consensus,
            "sprint3_score": {
                "total":     total,
                "max":       max_score,
                "pct":       round(total / max_score * 100, 1),
                "breakdown": {
                    "mm_flow": mm.confluence_score,
                    "wyckoff": wyk.confluence_score,
                    "ml":      ml.confluence_score,
                },
            },
            "mm_flow":  _mm_engine.to_dict(mm),
            "wyckoff":  _wyckoff_engine.to_dict(wyk),
            "ml_score": _ml_engine.to_dict(ml),
        }
    except Exception as e:
        logger.exception("Sprint 3 combined error")
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# SPRINT 4 Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/garch")
async def get_garch_forecast(req: GARCHRequest):
    """GARCH(1,1) volatility forecasting — regime, daily/weekly move estimates."""
    try:
        df = await _data_engine.get_candles(req.symbol, req.timeframe, limit=req.lookback)
        if df is None or df.empty:
            return {"error": "No candle data", "symbol": req.symbol}

        current_price = float(df["close"].iloc[-1])
        result = _garch_engine.analyze(df, current_price)
        return {
            "symbol":    req.symbol,
            "timeframe": req.timeframe,
            "price":     current_price,
            **_garch_engine.to_dict(result),
        }
    except Exception as e:
        logger.exception("GARCH error")
        return {"error": str(e)}


@router.post("/options")
async def get_options_analysis(req: OptionsRequest):
    """
    Black-Scholes options analysis + perp funding analysis.
    Computes ATM/OTM options, Greeks, put/call ratio, skew.
    """
    try:
        # Get current spot price
        df = await _data_engine.get_candles(req.symbol, "1h", limit=5)
        if df is None or df.empty:
            return {"error": "No price data", "symbol": req.symbol}

        spot = float(df["close"].iloc[-1])
        iv   = req.iv_30d_pct / 100

        result = _options_engine.analyze(
            spot_price=spot,
            iv_30d=iv,
            funding_rate_8h=req.funding_rate_8h,
            long_short_ratio=req.long_short_ratio,
        )
        return {
            "symbol": req.symbol,
            **_options_engine.to_dict(result),
        }
    except Exception as e:
        logger.exception("Options error")
        return {"error": str(e)}


@router.get("/signals")
async def get_active_signals(symbol: Optional[str] = Query(None)):
    """Get all active social trading signals."""
    try:
        signals = _social_engine.get_active_signals(symbol)
        return {
            "count":   len(signals),
            "signals": [_social_engine.signal_to_dict(s) for s in signals],
        }
    except Exception as e:
        logger.exception("Signals error")
        return {"error": str(e)}


@router.get("/leaderboard")
async def get_leaderboard(limit: int = Query(10, ge=1, le=50)):
    """Get trader leaderboard ranked by composite performance score."""
    try:
        leaders = _social_engine.get_leaderboard(limit)
        return {
            "count":       len(leaders),
            "leaderboard": [_social_engine.publisher_to_dict(p) for p in leaders],
        }
    except Exception as e:
        logger.exception("Leaderboard error")
        return {"error": str(e)}


@router.post("/publish-signal")
async def publish_signal(req: PublishSignalRequest):
    """Publish a new trading signal to the social feed."""
    try:
        signal = _social_engine.publish_signal(
            publisher_id=req.publisher_id,
            symbol=req.symbol,
            direction=req.direction,
            entry=req.entry,
            stop_loss=req.stop_loss,
            take_profits=req.take_profits,
            timeframe=req.timeframe,
            rationale=req.rationale,
            tags=req.tags,
        )
        return {
            "success": True,
            "signal":  _social_engine.signal_to_dict(signal),
        }
    except Exception as e:
        logger.exception("Publish signal error")
        return {"error": str(e)}


@router.post("/copy-trade")
async def calculate_copy_trade(req: CopyTradeRequest):
    """Calculate scaled position size for copying a signal."""
    try:
        # Find signal
        signal = _social_engine._signals.get(req.signal_id)
        if not signal:
            return {"error": f"Signal {req.signal_id} not found"}

        result = _social_engine.calculate_copy_trade(
            signal=signal,
            subscriber_balance=req.account_balance,
            risk_pct=req.risk_pct,
        )
        return {
            "signal_id":    req.signal_id,
            "account":      req.account_balance,
            "position_size":  result.position_size,
            "position_value": result.position_value,
            "risk_amount":    result.risk_amount,
            "stop_dist_pct":  result.stop_distance_pct,
            "rr_tp1":         result.tp1_rr,
            "rr_tp2":         result.tp2_rr,
            "match_score":    result.match_score,
            "warnings":       result.warnings,
        }
    except Exception as e:
        logger.exception("Copy trade error")
        return {"error": str(e)}


@router.get("/consensus/{symbol}")
async def get_consensus_signal(symbol: str):
    """Get consensus trading signal for a symbol from all active publishers."""
    try:
        consensus = _social_engine.get_consensus(symbol.upper())
        if not consensus:
            return {"symbol": symbol, "consensus": None, "message": "No active signals"}
        return {
            "symbol":    symbol,
            "direction": consensus.direction,
            "confidence_pct": consensus.confidence,
            "avg_entry": consensus.avg_entry,
            "avg_sl":    consensus.avg_sl,
            "avg_tp":    consensus.avg_tp,
            "avg_rr":    consensus.avg_rr,
            "publishers": consensus.publishers,
            "publisher_count": consensus.publisher_count,
            "tags":      consensus.tags,
            "quality":   consensus.signal_quality,
        }
    except Exception as e:
        logger.exception("Consensus error")
        return {"error": str(e)}


@router.post("/full-analysis")
async def get_full_advanced_analysis(req: AdvancedFullAnalysisRequest):
    """
    Complete Sprint 3+4 analysis in one call:
    MM Flow + Wyckoff + ML + GARCH + Options + Social Consensus.
    """
    try:
        symbol = req.symbol.upper()

        df_entry = await _data_engine.get_candles(symbol, req.timeframe, limit=150)
        df_htf   = await _data_engine.get_candles(symbol, req.htf, limit=100)

        if df_entry is None or df_entry.empty:
            return {"error": "No price data", "symbol": symbol}

        price = float(df_entry["close"].iloc[-1])

        # Run all engines
        mm    = _mm_engine.analyze(df_entry)
        wyk   = _wyckoff_engine.analyze(df_htf if df_htf is not None and not df_htf.empty else df_entry)
        ml    = _ml_engine.analyze(df_entry)
        garch = _garch_engine.analyze(df_entry, price)
        opts  = _options_engine.analyze(
            spot_price=price,
            iv_30d=req.iv_30d_pct / 100,
            funding_rate_8h=req.funding_rate_8h,
        )
        consensus = _social_engine.get_consensus(symbol)

        # Mega confluence score
        scores = {
            "mm_flow":  mm.confluence_score,
            "wyckoff":  wyk.confluence_score,
            "ml":       ml.confluence_score,
            "garch":    garch.confluence_score,
            "options":  opts.confluence_score,
            "social":   3 if consensus and consensus.signal_quality == "HIGH_CONVICTION" else
                        1 if consensus else 0,
        }
        total = sum(scores.values())
        max_s = 30

        grade = ("A+" if total >= 22 else "A" if total >= 17 else
                 "B"  if total >= 12 else "C" if total >= 7  else "WEAK")

        return {
            "symbol":    symbol,
            "timeframe": req.timeframe,
            "price":     price,

            "mm_flow":  _mm_engine.to_dict(mm),
            "wyckoff":  _wyckoff_engine.to_dict(wyk),
            "ml_score": _ml_engine.to_dict(ml),
            "garch":    _garch_engine.to_dict(garch),
            "options":  _options_engine.to_dict(opts),
            "social": {
                "consensus":        consensus.direction if consensus else None,
                "confidence_pct":   consensus.confidence if consensus else 0,
                "signal_quality":   consensus.signal_quality if consensus else "NONE",
                "publisher_count":  consensus.publisher_count if consensus else 0,
            },

            "mega_confluence": {
                "total_score":   total,
                "max_score":     max_s,
                "score_pct":     round(total / max_s * 100, 1),
                "grade":         grade,
                "breakdown":     scores,
                "signal": (
                    "ULTRA HIGH CONVICTION" if total >= 22 else
                    "HIGH CONVICTION"       if total >= 17 else
                    "VALID SETUP"           if total >= 12 else
                    "WATCHLIST"             if total >= 7  else
                    "NO CLEAR EDGE"
                ),
            },
        }
    except Exception as e:
        logger.exception("Full advanced analysis error")
        return {"error": str(e)}
