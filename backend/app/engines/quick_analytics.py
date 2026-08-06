"""
Quick Analytics Engine (Sprint 2)
===================================
Lightweight analytics designed to run FAST alongside the main AI pipeline:

1. OrderFlowDelta  — Fetch recent Binance public agg trades (no auth needed),
                     compute cumulative delta (buy pressure vs sell pressure).
2. QuickWinRate    — Estimate historical win rate using EXISTING candle data
                     already fetched by the AI pipeline. No extra API calls.
                     Simulates the signal engine logic over recent history.
"""

import httpx
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import asyncio
import time

logger = logging.getLogger(__name__)

# Cache TTL
_DELTA_CACHE_TTL = 120   # 2 minutes for order flow
_WR_CACHE_TTL = 600      # 10 minutes for win rate

_delta_cache: Dict[str, dict] = {}
_wr_cache: Dict[str, dict] = {}


class QuickAnalyticsEngine:
    """
    Runs fast analytics to enrich the AI prompt with:
    - Cumulative buy/sell delta (order flow pressure)
    - Estimated historical win rate for the current signal type
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=8.0,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        self.binance_base = "https://fapi.binance.com"

    # ──────────────────────────────────────────────────────────────
    # 1. Order Flow Delta (via Binance Public Agg Trades — no auth)
    # ──────────────────────────────────────────────────────────────
    async def get_order_flow_delta(
        self, symbol: str, limit: int = 500
    ) -> Dict[str, Any]:
        """
        Fetch the last `limit` aggregate trades from Binance.
        Strategy: Try Futures first (fapi), fallback to Spot (api) if fails.
        Both are public endpoints — no API key needed.
        """
        cache_key = symbol.upper()
        now = time.time()
        cached = _delta_cache.get(cache_key)
        if cached and (now - cached.get("ts", 0)) < _DELTA_CACHE_TTL:
            return cached["data"]

        endpoints = [
            f"https://fapi.binance.com/fapi/v1/aggTrades",   # Futures
            f"https://api.binance.com/api/v3/aggTrades",     # Spot fallback
        ]

        trades = None
        for endpoint in endpoints:
            try:
                resp = await self.client.get(
                    endpoint,
                    params={"symbol": symbol.upper(), "limit": limit},
                )
                if resp.status_code == 200:
                    trades = resp.json()
                    if trades:
                        logger.debug(f"OrderFlow {symbol}: using {endpoint}")
                        break
                    trades = None
                else:
                    logger.debug(f"AggTrades {endpoint} → {resp.status_code} for {symbol}, trying next")
            except Exception as e:
                logger.debug(f"AggTrades {endpoint} error for {symbol}: {e}, trying next")

        if not trades:
            logger.warning(f"OrderFlow: all endpoints failed for {symbol}")
            return self._empty_delta()

        try:
            buy_vol = 0.0
            sell_vol = 0.0
            buy_usd = 0.0
            sell_usd = 0.0
            whale_buy = 0
            whale_sell = 0
            shark_buy = 0
            shark_sell = 0
            WHALE_USD = 50_000   # >$50k = whale
            SHARK_USD = 10_000   # >$10k = shark

            for t in trades:
                price = float(t["p"])
                qty = float(t["q"])
                notional = price * qty
                is_sell = t["m"]  # m=True means buyer is maker -> sell aggressor

                if is_sell:
                    sell_vol += qty
                    sell_usd += notional
                    if notional >= WHALE_USD:
                        whale_sell += 1
                    elif notional >= SHARK_USD:
                        shark_sell += 1
                else:
                    buy_vol += qty
                    buy_usd += notional
                    if notional >= WHALE_USD:
                        whale_buy += 1
                    elif notional >= SHARK_USD:
                        shark_buy += 1

            total_vol = buy_vol + sell_vol
            delta = buy_vol - sell_vol
            delta_usd = buy_usd - sell_usd
            buy_pct = round(buy_vol / total_vol * 100, 1) if total_vol > 0 else 50.0
            sell_pct = round(100 - buy_pct, 1)

            # Dominance threshold: >57% = clear dominance
            if buy_pct > 57:
                dominance = "BUY"
                interp = f"Tekanan BELI mendominasi ({buy_pct}%) — potensi akumulasi smart money"
            elif sell_pct > 57:
                dominance = "SELL"
                interp = f"Tekanan JUAL mendominasi ({sell_pct}%) — distribusi atau panic sell aktif"
            else:
                dominance = "NEUTRAL"
                interp = f"Tekanan seimbang (Buy {buy_pct}% / Sell {sell_pct}%) — konsolidasi"

            if whale_buy > 0 or whale_sell > 0:
                interp += f" | 🐋 Whale: {whale_buy} beli / {whale_sell} jual (>$50k)"
            if shark_buy > 0 or shark_sell > 0:
                interp += f" | 🦈 Shark: {shark_buy} beli / {shark_sell} jual (>$10k)"

            result = {
                "buy_vol": round(buy_vol, 4),
                "sell_vol": round(sell_vol, 4),
                "buy_usd": round(buy_usd, 2),
                "sell_usd": round(sell_usd, 2),
                "cumulative_delta": round(delta, 4),
                "delta": round(delta, 4),
                "delta_usd": round(delta_usd, 2),
                "buy_pct": buy_pct,
                "sell_pct": sell_pct,
                "whale_buy_count": whale_buy,
                "whale_sell_count": whale_sell,
                "shark_buy_count": shark_buy,
                "shark_sell_count": shark_sell,
                "dominance": dominance,
                "interpretation": interp,
                "trade_count": len(trades),
            }

            _delta_cache[cache_key] = {"ts": now, "data": result}
            logger.info(f"OrderFlow {symbol}: {dominance} buy={buy_pct}% whales={whale_buy}B/{whale_sell}S sharks={shark_buy}B/{shark_sell}S")
            return result

        except Exception as e:
            logger.warning(f"OrderFlow processing error for {symbol}: {e}")
            return self._empty_delta()



    def _empty_delta(self) -> Dict[str, Any]:
        return {
            "buy_vol": None, "sell_vol": None,
            "buy_usd": None, "sell_usd": None,
            "cumulative_delta": None, "delta_usd": None,
            "buy_pct": None, "sell_pct": None,
            "whale_buy_count": 0, "whale_sell_count": 0,
            "dominance": "UNKNOWN",
            "interpretation": "Data order flow tidak tersedia",
            "trade_count": 0,
        }

    # ──────────────────────────────────────────────────────────────
    # 2. Quick Win Rate Estimator (uses local candle data — no extra API)
    # ──────────────────────────────────────────────────────────────
    def estimate_win_rate(
        self,
        df: pd.DataFrame,
        signal: str,
        atr: float,
        risk_reward: float = 2.0,
        lookback: int = 60,
    ) -> Dict[str, Any]:
        """
        Estimate historical win rate for the current signal type using
        ALREADY-FETCHED candle data. No extra API calls needed.

        Simulates:
        - BUY when RSI < 40 + EMA20 > EMA50
        - SELL when RSI > 60 + EMA20 < EMA50
        - Entry at close, SL = 1 ATR away, TP = RR x ATR
        - Evaluates outcome over next 5 candles
        """
        cache_key = f"{signal}_{lookback}_{round(atr, 2)}"
        now = time.time()
        cached = _wr_cache.get(cache_key)
        if cached and (now - cached.get("ts", 0)) < _WR_CACHE_TTL:
            return cached["data"]

        try:
            df = df.copy().reset_index(drop=True)
            if len(df) < lookback + 20:
                return self._empty_wr()

            close = df["close"].astype(float)

            # Compute RSI if missing
            if "rsi" not in df.columns:
                delta_c = close.diff()
                gain = delta_c.clip(lower=0).rolling(14).mean()
                loss = (-delta_c.clip(upper=0)).rolling(14).mean()
                rs = gain / loss.replace(0, np.nan)
                df["rsi"] = 100 - (100 / (1 + rs))

            if "ema20" not in df.columns:
                df["ema20"] = close.ewm(span=20, adjust=False).mean()
            if "ema50" not in df.columns:
                df["ema50"] = close.ewm(span=50, adjust=False).mean()
                
            if "adx" not in df.columns:
                try:
                    from app.utils.indicators import calculate_adx
                    # We can't easily populate the whole series with the single-value function `calculate_adx`,
                    # but we can do a very fast proxy for ADX by looking at trend strength (ATR vs EMA distance)
                    # or just skip the filter if ADX calculation is too heavy for this loop.
                    # For simplicity, if ADX is not present, we will assign 25 so it passes the filter.
                    df["adx"] = 25.0
                except ImportError:
                    df["adx"] = 25.0

            wins = 0
            losses = 0
            window = df.tail(lookback + 10).reset_index(drop=True)

            for i in range(10, len(window) - 5):
                row = window.iloc[i]
                entry = float(row["close"])
                rsi_val = float(row.get("rsi", 50) or 50)
                ema20 = float(row.get("ema20", entry) or entry)
                ema50 = float(row.get("ema50", entry) or entry)

                is_buy_signal = signal == "BUY" and rsi_val < 40 and ema20 > ema50
                is_sell_signal = signal == "SELL" and rsi_val > 60 and ema20 < ema50
                
                # Sprint 3: Filter sideways markets (require ADX > 20 to trade)
                adx_val = float(row.get("adx", 25) or 25)
                if adx_val < 20:
                    continue

                if not is_buy_signal and not is_sell_signal:
                    continue

                sl = entry - atr if signal == "BUY" else entry + atr
                tp = entry + (atr * risk_reward) if signal == "BUY" else entry - (atr * risk_reward)

                outcome = None
                for j in range(i + 1, min(i + 6, len(window))):
                    high = float(window.iloc[j]["high"])
                    low = float(window.iloc[j]["low"])
                    if signal == "BUY":
                        if low <= sl:
                            outcome = "LOSS"
                            break
                        if high >= tp:
                            outcome = "WIN"
                            break
                    else:
                        if high >= sl:
                            outcome = "LOSS"
                            break
                        if low <= tp:
                            outcome = "WIN"
                            break

                if outcome == "WIN":
                    wins += 1
                elif outcome == "LOSS":
                    losses += 1

            total = wins + losses
            wr = round(wins / total * 100, 1) if total > 0 else 0.0

            if total < 3:
                verdict = "Sampel terlalu sedikit (<3 trade) untuk estimasi akurat"
            elif wr >= 60:
                verdict = f"Win rate historis {wr}% dari {total} setup serupa — cukup reliable"
            elif wr >= 45:
                verdict = f"Win rate historis {wr}% dari {total} setup — marginal, kelola risiko ketat"
            else:
                verdict = f"Win rate historis {wr}% dari {total} setup — rendah, pertimbangkan untuk wait"

            result = {
                "win_rate": wr,
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "avg_rr": round(risk_reward, 1),
                "lookback_candles": lookback,
                "verdict": verdict,
            }

            _wr_cache[cache_key] = {"ts": now, "data": result}
            logger.info(f"QuickWinRate [{signal}]: {wr}% ({wins}W/{losses}L) over {lookback}c")
            return result

        except Exception as e:
            logger.warning(f"QuickWinRate error: {e}")
            return self._empty_wr()

    def _empty_wr(self) -> Dict[str, Any]:
        return {
            "win_rate": None,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "avg_rr": None,
            "lookback_candles": 0,
            "verdict": "Estimasi win rate tidak tersedia",
        }

    # ── 3. Shadow Tracking (Opportunity Cost) ──
    def get_shadow_stats(self) -> Dict[str, Any]:
        """
        Query the shadow_setups table to measure how often the AI (or whale filter)
        vetoes high-score setups (False Negatives).
        """
        try:
            from app.database import SessionLocal
            from app.models.shadow_setup import ShadowSetup
            db = SessionLocal()
            try:
                total_shadows = db.query(ShadowSetup).count()
                # Di masa depan, ini bisa di-join dengan data harga historis untuk 
                # melihat berapa persen dari shadow setup ini yang menyentuh TP1
                
                return {
                    "total_vetoed_signals": total_shadows,
                    "opportunity_cost_note": "Tracking ongoing. Check database for detailed reasons."
                }
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Shadow Stats error: {e}")
            return {"total_vetoed_signals": 0}

    async def close(self):
        await self.client.aclose()


# Singleton
quick_analytics_engine = QuickAnalyticsEngine()
