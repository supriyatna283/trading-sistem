"""
Trading Setup Generator (V5 - Hardened Quality Gates)
==============================================================
Generates trade ideas based on SMC, Confluence, and Market Intelligence.
- Minimum confluence score: 12/24 (50% confluence required)
- Minimum R:R ratio: 1.8
- Mandatory core gates: HTF alignment + structure + SMC (OB/Liq)
- OB proximity validation before entry generation
- Structure-based SL placement with ATR fallback
- Enriches signal explanation with market intel details.
- V5.1: Per-gate debug logging for full observability.
"""

import logging
import pandas as pd
import numpy as np
from typing import Optional, List, Dict
from app.schemas.trade_setup import TradeSetupSchema, ConfluenceResult
from app.schemas.market_data import SmartMoneyAnalysis, MarketBias

logger = logging.getLogger(__name__)


def _estimate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Estimate ATR from OHLCV data."""
    if df.empty or len(df) < 2:
        return 0.0
    highs = df["high"].astype(float).values
    lows = df["low"].astype(float).values
    closes = df["close"].astype(float).values
    trs = []
    for i in range(1, len(df)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    if not trs:
        return 0.0
    return sum(trs[-period:]) / min(period, len(trs))


def _find_nearest_swing_low(df: pd.DataFrame, reference_price: float, lookback: int = 20) -> Optional[float]:
    """Find the nearest swing low below the reference price (3-bar pivot)."""
    if df.empty or len(df) < 5:
        return None
    lows = df["low"].astype(float).values[-lookback:]
    swing_lows = [
        lows[i] for i in range(2, len(lows) - 2)
        if lows[i] < lows[i-1] and lows[i] < lows[i-2]
        and lows[i] < lows[i+1] and lows[i] < lows[i+2]
        and lows[i] < reference_price
    ]
    return max(swing_lows) if swing_lows else None


def _find_nearest_swing_high(df: pd.DataFrame, reference_price: float, lookback: int = 20) -> Optional[float]:
    """Find the nearest swing high above the reference price (3-bar pivot)."""
    if df.empty or len(df) < 5:
        return None
    highs = df["high"].astype(float).values[-lookback:]
    swing_highs = [
        highs[i] for i in range(2, len(highs) - 2)
        if highs[i] > highs[i-1] and highs[i] > highs[i-2]
        and highs[i] > highs[i+1] and highs[i] > highs[i+2]
        and highs[i] > reference_price
    ]
    return min(swing_highs) if swing_highs else None


def calculate_trade_levels(
    direction: str, last_price: float, smc, df: pd.DataFrame,
    df_15m: Optional[pd.DataFrame] = None,
    sr_data: Optional[Dict] = None,
) -> tuple:
    """
    Canonical level calculator — SHARED by Setup Engine AND AI Analysis.
    Uses OB-based entry zones + structure-based SL + 2R/3R/4.5R TP targets.

    V7 Improvements:
    - S/R-Aware Entry: Entry zone snapped to nearest Support (BUY) or
      Resistance (SELL) if it falls within 1.5×ATR of the OB zone.
      Institutional players accumulate/distribute exactly AT these levels.
    - S/R TP Snap: TP1/TP2 automatically snapped to the nearest S/R target
      within 3% of the default 2R/3R levels — more realistic profit targets.
    - V6: Volatility-Adjusted SL + MTER 15m (still active).

    Returns: (entry_low, entry_high, sl, tp1, tp2, tp3)
    """
    recent = df.tail(20)
    atr = _estimate_atr(recent)
    if atr == 0:
        atr = float(df["high"].astype(float).values[-1] - df["low"].astype(float).values[-1]) * 2

    # ATR floor for SL: minimum distance = 1.5 × ATR (prevents SL too tight)
    atr_sl_floor = atr * 1.5

    if direction == "BUY":
        bullish_obs = [ob for ob in smc.order_blocks if ob.type == "BULLISH" and not ob.mitigated]
        reachable_obs = [ob for ob in bullish_obs if abs(last_price - ob.low) <= atr * 3]
        if reachable_obs:
            ob = reachable_obs[-1]
            entry_low = ob.low
            entry_high = ob.high
        else:
            entry_low = last_price - atr * 0.3
            entry_high = last_price

        # MTER: Refine entry zone using 15m OB if available
        if df_15m is not None and not df_15m.empty:
            try:
                from app.engines.smart_money import SmartMoneyConceptsEngine
                smc_15m = SmartMoneyConceptsEngine().analyze(df_15m.tail(100), "", "15m")
                # Find 15m bullish OB within HTF entry zone
                htf_zone_obs = [
                    ob for ob in smc_15m.order_blocks
                    if ob.type == "BULLISH" and not ob.mitigated
                    and ob.low >= entry_low * 0.995  # within 0.5% below entry_low
                    and ob.high <= entry_high * 1.01
                ]
                if htf_zone_obs:
                    refined_ob = htf_zone_obs[-1]
                    entry_low = refined_ob.low
                    entry_high = refined_ob.high
                    logger.debug(f"MTER 15m: Entry refined to [{entry_low:.4f} - {entry_high:.4f}]")
            except Exception:
                pass  # MTER is optional enhancement, never block setup generation

        swing_low = _find_nearest_swing_low(df, entry_low)
        structure_sl = (swing_low - atr * 0.15) if (swing_low is not None and swing_low < entry_low) else (entry_low - atr * 1.0)
        # Volatility-Adjusted SL: use whichever gives MORE room (further from entry)
        atr_based_sl = entry_low - atr_sl_floor
        sl = min(structure_sl, atr_based_sl)  # min = further below for BUY

        risk = entry_low - sl
        tp1 = entry_high + risk * 2.0
        tp2 = entry_high + risk * 3.0
        tp3 = entry_high + risk * 4.5

    else:  # SELL
        bearish_obs = [ob for ob in smc.order_blocks if ob.type == "BEARISH" and not ob.mitigated]
        reachable_obs = [ob for ob in bearish_obs if abs(ob.high - last_price) <= atr * 3]
        if reachable_obs:
            ob = reachable_obs[-1]
            entry_low = ob.low
            entry_high = ob.high
        else:
            entry_low = last_price
            entry_high = last_price + atr * 0.3

        # MTER: Refine entry zone using 15m OB if available
        if df_15m is not None and not df_15m.empty:
            try:
                from app.engines.smart_money import SmartMoneyConceptsEngine
                smc_15m = SmartMoneyConceptsEngine().analyze(df_15m.tail(100), "", "15m")
                htf_zone_obs = [
                    ob for ob in smc_15m.order_blocks
                    if ob.type == "BEARISH" and not ob.mitigated
                    and ob.low >= entry_low * 0.99
                    and ob.high <= entry_high * 1.005
                ]
                if htf_zone_obs:
                    refined_ob = htf_zone_obs[-1]
                    entry_low = refined_ob.low
                    entry_high = refined_ob.high
                    logger.debug(f"MTER 15m: Entry refined to [{entry_low:.4f} - {entry_high:.4f}]")
            except Exception:
                pass

        swing_high = _find_nearest_swing_high(df, entry_high)
        structure_sl = (swing_high + atr * 0.15) if (swing_high is not None and swing_high > entry_high) else (entry_high + atr * 1.0)
        # Volatility-Adjusted SL: use whichever gives MORE room (further from entry)
        atr_based_sl = entry_high + atr_sl_floor
        sl = max(structure_sl, atr_based_sl)  # max = further above for SELL

        risk = sl - entry_high
        tp1 = entry_low - risk * 2.0
        tp2 = entry_low - risk * 3.0
        tp3 = entry_low - risk * 4.5

    # ── S/R SNAP HELPER ──────────────────────────────────────────────────────
    def _snap_to_sr(price: float, levels: list, threshold_pct: float = 3.0) -> float:
        """Snap a price to the nearest S/R level if within threshold_pct."""
        if not levels:
            return price
        nearest = min(levels, key=lambda lvl: abs(lvl - price))
        if abs(nearest - price) / price * 100 <= threshold_pct:
            logger.debug(f"S/R Snap: {price:.6f} → {nearest:.6f} (within {threshold_pct}%)")
            return nearest
        return price

    # Parse S/R levels from market intel data
    supports = sr_data.get("supports", []) if sr_data else []
    resistances = sr_data.get("resistances", []) if sr_data else []
    nearest_support = sr_data.get("nearest_support", 0) if sr_data else 0
    nearest_resistance = sr_data.get("nearest_resistance", 0) if sr_data else 0

    if direction == "BUY":
        # ── BUY Entry: Snap entry_low to nearest Support within 1.5×ATR ──────
        if nearest_support > 0 and abs(nearest_support - entry_low) <= atr * 1.5:
            old = entry_low
            entry_low = nearest_support
            # Keep entry_high slightly above support zone
            entry_high = max(entry_high, entry_low + atr * 0.2)
            logger.debug(f"S/R BUY Entry Snap: {old:.6f} → entry_low={entry_low:.6f} (Support)")

        # ── BUY TP Snap: Snap TP1 to nearest Resistance ───────────────────────
        # TP1 should stop just BELOW resistance (−0.1% buffer), not above it
        tp_resistances = [r for r in resistances if r > entry_high]
        if tp_resistances:
            nearest_tp_r = min(tp_resistances, key=lambda r: abs(r - tp1))
            if abs(nearest_tp_r - tp1) / max(tp1, 1) * 100 <= 5.0:  # within 5%
                tp1 = nearest_tp_r * 0.999  # just below resistance
                logger.debug(f"S/R BUY TP1 Snap: → {tp1:.6f} (below Resistance {nearest_tp_r:.6f})")
            # TP2 snap to next resistance level
            tp2_resistances = [r for r in resistances if r > tp1 * 1.005]
            if tp2_resistances:
                nearest_tp2_r = min(tp2_resistances, key=lambda r: abs(r - tp2))
                if abs(nearest_tp2_r - tp2) / max(tp2, 1) * 100 <= 8.0:
                    tp2 = nearest_tp2_r * 0.999
                    logger.debug(f"S/R BUY TP2 Snap: → {tp2:.6f}")

    else:  # SELL
        # ── SELL Entry: Snap entry_high to nearest Resistance within 1.5×ATR ─
        if nearest_resistance > 0 and abs(nearest_resistance - entry_high) <= atr * 1.5:
            old = entry_high
            entry_high = nearest_resistance
            entry_low = min(entry_low, entry_high - atr * 0.2)
            logger.debug(f"S/R SELL Entry Snap: {old:.6f} → entry_high={entry_high:.6f} (Resistance)")

        # ── SELL TP Snap: Snap TP1 to nearest Support ────────────────────────
        tp_supports = [s for s in supports if s < entry_low]
        if tp_supports:
            nearest_tp_s = min(tp_supports, key=lambda s: abs(s - tp1))
            if abs(nearest_tp_s - tp1) / max(abs(tp1), 1) * 100 <= 5.0:
                tp1 = nearest_tp_s * 1.001  # just above support
                logger.debug(f"S/R SELL TP1 Snap: → {tp1:.6f} (above Support {nearest_tp_s:.6f})")
            tp2_supports = [s for s in supports if s < tp1 * 0.995]
            if tp2_supports:
                nearest_tp2_s = min(tp2_supports, key=lambda s: abs(s - tp2))
                if abs(nearest_tp2_s - tp2) / max(abs(tp2), 1) * 100 <= 8.0:
                    tp2 = nearest_tp2_s * 1.001
                    logger.debug(f"S/R SELL TP2 Snap: → {tp2:.6f}")

    return entry_low, entry_high, sl, tp1, tp2, tp3


class SetupGenerator:
    """V5 — Generates actionable trading setups with hardened quality gates."""

    def __init__(self, min_confluence_score: int = 18, min_rr: float = 1.8):
        self.min_score = min_confluence_score
        self.min_rr = min_rr

    def generate(
        self,
        symbol: str,
        timeframe: str,
        confluence: ConfluenceResult,
        smc: SmartMoneyAnalysis,
        structure: MarketBias,
        df: pd.DataFrame,
        mtf_result: Optional[Dict] = None,
        news_events: Optional[List[Dict]] = None,
        sentiment_data: Optional[Dict] = None,
        market_intel_data: Optional[Dict] = None,
        volume_delta: Optional[float] = None,
        df_15m: Optional[pd.DataFrame] = None,
        rsi_4h: Optional[float] = None,
        market_regime: Optional[str] = None,
    ) -> Optional[TradeSetupSchema]:
        """Generate a setup ONLY if ALL quality gates pass."""

        def _reject(gate: str, reason: str):
            logger.debug(
                f"[{symbol}/{timeframe}] ❌ Gate={gate} | Score={confluence.total_score}/{confluence.max_score} "
                f"| Rec={confluence.recommendation} | Reason: {reason}"
            )

        # ---- Quality Gate 1: Minimum Confluence Score ----
        if confluence.total_score < self.min_score:
            _reject("min_score", f"score={confluence.total_score} < required={self.min_score}")
            return None

        # ---- Quality Gate 2: Must have a clear direction ----
        if confluence.recommendation in ("NEUTRAL",):
            _reject("direction", f"recommendation={confluence.recommendation}")
            return None

        if df.empty or len(df) < 20:
            _reject("data", "insufficient candles (<20)")
            return None

        direction = "BUY" if confluence.recommendation in ("BUY", "STRONG_BUY") else "SELL"

        # ---- Quality Gate 3: HTF Bias Lock ----
        # V6: Hardened — 4H is the DOMINANT timeframe for 1H entries.
        # If 4H is opposite to direction, REJECT unless there's a strong reversal exception:
        #   - BUY despite 4H BEARISH: only if RSI 4H < 20 (extreme oversold divergence)
        #   - SELL despite 4H BULLISH: only if RSI 4H > 80 (extreme overbought divergence)
        htf_details = confluence.details.get("htf_bias", {})
        htf_biases = htf_details.get("biases", {})  # e.g. {"1d": "BULLISH", "4h": "BEARISH"}
        if htf_biases:
            htf_4h_bias = htf_biases.get("4h", "SIDEWAYS")
            htf_1d_bias = htf_biases.get("1d", "SIDEWAYS")
            opposite = "BEARISH" if direction == "BUY" else "BULLISH"

            # Dominant bias = 4H (more relevant to 1H entries)
            dominant_opposite = htf_4h_bias == opposite
            reinforcing_opposite = htf_1d_bias == opposite

            if dominant_opposite:
                # 4H is against us — check if RSI extreme provides reversal exception
                reversal_exception = False
                if rsi_4h is not None:
                    if direction == "BUY" and rsi_4h < 20:  # Extreme oversold
                        reversal_exception = True
                        logger.debug(f"[{symbol}] HTF lock exception: BUY vs 4H BEARISH allowed (RSI4H={rsi_4h:.1f} < 20)")
                    elif direction == "SELL" and rsi_4h > 80:  # Extreme overbought
                        reversal_exception = True
                        logger.debug(f"[{symbol}] HTF lock exception: SELL vs 4H BULLISH allowed (RSI4H={rsi_4h:.1f} > 80)")

                if not reversal_exception:
                    _reject("htf_bias_lock", f"4H bias={htf_4h_bias} opposes direction={direction}, no RSI extreme exception (rsi_4h={rsi_4h})")
                    return None

            elif reinforcing_opposite and not dominant_opposite:
                # 4H agrees but 1D opposes — allow but flag (partial alignment)
                logger.debug(f"[{symbol}] HTF partial conflict: 4H={htf_4h_bias}, 1D={htf_1d_bias}, direction={direction} (proceeding)")

        # ---- Quality Gate 4: Need SMC edge OR structure confirmation ----
        # (NOT both — big caps may not always be in an OB but still have valid BOS)
        has_smc_edge = (
            confluence.details.get("liquidity", {}).get("swept", False)
            or confluence.details.get("order_block", {}).get("in_zone", False)
        )
        has_structure = confluence.details.get("structure", {}).get("confirmed", False)
        has_fvg = confluence.details.get("fvg", {}).get("present", False)

        # Must have at least ONE technical anchor
        if not has_smc_edge and not has_structure and not has_fvg:
            _reject("technical_anchor", "no OB, no liquidity sweep, no FVG, no BOS/CHOCH")
            return None

        # Phase 3: Volume Delta Mandatory Filter (if order flow data is available)
        if volume_delta is not None:
            if direction == "BUY" and volume_delta < 0:
                _reject("volume_delta", f"direction=BUY but volume_delta={volume_delta} < 0")
                return None
            if direction == "SELL" and volume_delta > 0:
                _reject("volume_delta", f"direction=SELL but volume_delta={volume_delta} > 0")
                return None

        last_price = float(df.iloc[-1]["close"])
        # V7: Extract S/R data from market intel for entry/TP snapping
        sr_data = market_intel_data.get("support_resistance") if market_intel_data else None
        entry_low, entry_high, sl, tp1, tp2, tp3 = calculate_trade_levels(
            direction, last_price, smc, df, df_15m=df_15m, sr_data=sr_data
        )

        risk = abs(entry_low - sl) if direction == "BUY" else abs(sl - entry_high)
        reward = abs(tp1 - entry_high) if direction == "BUY" else abs(entry_low - tp1)
        rr = round(reward / risk, 2) if risk > 0 else 0

        if rr < self.min_rr:
            _reject("rr_ratio", f"rr={rr} < required={self.min_rr}")
            return None

        # ---- Quality Gate 5: Stop loss sanity check ----
        # Big caps are naturally more volatile; allow wider SL to avoid premature rejection
        tier1_pairs = {"BTCUSDT", "ETHUSDT"}          # Top 2: allow up to 5%
        tier2_pairs = {"BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT"}
        if symbol.upper() in tier1_pairs:
            max_sl_pct = 5.0
        elif symbol.upper() in tier2_pairs:
            max_sl_pct = 4.0
        else:
            max_sl_pct = 6.0  # Alts can have wider swings
        sl_distance_pct = abs(sl - last_price) / last_price * 100
        if sl_distance_pct > max_sl_pct:
            _reject("sl_distance", f"sl_pct={sl_distance_pct:.2f}% > max={max_sl_pct}%")
            return None

        # Macro filters (MTF, News, Sentiment) are now considered inside the confluence score
        # rather than being strict blockers, to maximize signal generation based on core technicals.

        # Build detailed explanation (V4 — includes market intel)
        explanation = self._build_explanation(confluence, direction, rr, market_intel_data, volume_delta)
        setup_type = self._build_setup_type(confluence, direction)

        logger.info(
            f"[{symbol}/{timeframe}] ✅ Setup ACCEPTED | {direction} | "
            f"Score={confluence.total_score}/{confluence.max_score} | R:R=1:{rr} | "
            f"Entry={round(entry_low,4)}-{round(entry_high,4)} | SL={round(sl,4)} | TP1={round(tp1,4)}"
        )

        return TradeSetupSchema(
            symbol=symbol,
            direction=direction,
            entry_low=round(entry_low, 8),
            entry_high=round(entry_high, 8),
            stop_loss=round(sl, 8),
            take_profit_1=round(tp1, 8),
            take_profit_2=round(tp2, 8) if tp2 else None,
            take_profit_3=round(tp3, 8) if tp3 else None,
            risk_reward=rr,
            setup_type=setup_type,
            confluence_score=confluence.total_score,
            status="ACTIVE",
            timeframe=timeframe,
            explanation=explanation,
        )

    def _calculate_levels(
        self, direction: str, last_price: float,
        smc: SmartMoneyAnalysis, df: pd.DataFrame,
        df_15m: Optional[pd.DataFrame] = None,
    ):
        """Delegate to the shared canonical level calculator."""
        return calculate_trade_levels(direction, last_price, smc, df, df_15m=df_15m)

    @staticmethod
    def _find_nearest_swing_low(df: pd.DataFrame, reference_price: float, lookback: int = 20) -> Optional[float]:
        """
        Find the nearest swing low below the reference price.
        Uses a 3-bar pivot low detection within the lookback window.
        """
        if df.empty or len(df) < 5:
            return None
        lows = df["low"].astype(float).values[-lookback:]
        swing_lows = []
        for i in range(2, len(lows) - 2):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                if lows[i] < reference_price:
                    swing_lows.append(lows[i])
        if not swing_lows:
            return None
        # Return the nearest (highest) swing low below reference
        return max(swing_lows)

    @staticmethod
    def _find_nearest_swing_high(df: pd.DataFrame, reference_price: float, lookback: int = 20) -> Optional[float]:
        """
        Find the nearest swing high above the reference price.
        Uses a 3-bar pivot high detection within the lookback window.
        """
        if df.empty or len(df) < 5:
            return None
        highs = df["high"].astype(float).values[-lookback:]
        swing_highs = []
        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                if highs[i] > reference_price:
                    swing_highs.append(highs[i])
        if not swing_highs:
            return None
        # Return the nearest (lowest) swing high above reference
        return min(swing_highs)

    def _build_explanation(self, confluence: ConfluenceResult, direction: str, rr: float, market_intel_data: Optional[Dict] = None, volume_delta: Optional[float] = None) -> str:
        """Build a professional explanation string."""
        parts = []
        details = confluence.details

        if details.get("htf_bias", {}).get("aligned"):
            biases = details["htf_bias"]["biases"]
            parts.append(f"HTF Bias aligned ({', '.join(f'{k}: {v}' for k, v in biases.items())})")

        if details.get("liquidity", {}).get("swept"):
            count = details["liquidity"]["swept_count"]
            parts.append(f"Liquidity swept ({count} level{'s' if count > 1 else ''})")

        if details.get("order_block", {}).get("in_zone"):
            ob_dir = details["order_block"].get("ob_direction", direction)
            parts.append(f"Price in fresh {ob_dir} Order Block zone")

        if details.get("fvg", {}).get("present"):
            parts.append(f"Unfilled FVG present ({details['fvg']['aligned_count']} aligned)")

        if details.get("structure", {}).get("confirmed"):
            parts.append(f"Structure confirmed ({details['structure']['bias']})")

        if details.get("premium_discount", {}).get("in_correct_zone"):
            zone = "Discount" if direction == "BUY" else "Premium"
            parts.append(f"Price in {zone} zone")

        if details.get("volume", {}).get("confirmed"):
            parts.append("Volume spike confirmed (2x+)")

        if details.get("session", {}).get("in_session"):
            parts.append("Active session (London/NY)")

        if details.get("mtf_confirmation", {}).get("confirmed"):
            level = details["mtf_confirmation"].get("level", "MODERATE")
            parts.append(f"MTF {level} confirmation")

        if details.get("news", {}).get("clear"):
            parts.append("No high-impact news")

        if details.get("sentiment", {}).get("aligned"):
            parts.append("Sentiment aligned")

        if details.get("rsi", {}).get("aligned"):
            val = details["rsi"].get("value", 0)
            parts.append(f"RSI confirmed ({val})")

        if details.get("ema", {}).get("aligned"):
            parts.append("Trend aligned (200 EMA)")

        if details.get("macd", {}).get("aligned"):
            parts.append("MACD Momentum aligned")

        # --- Phase 3: Power Features ---
        if details.get("adx", {}).get("value") is not None:
            adx = details["adx"]["value"]
            parts.append(f"ADX Trend Strength: {adx}")

        if details.get("candle_pattern", {}).get("aligned"):
            pattern = details["candle_pattern"].get("pattern", "unknown").replace("_", " ").title()
            parts.append(f"Candle Pattern Confirmed: {pattern}")

        if details.get("open_interest", {}).get("aligned"):
            parts.append(f"Open Interest Increasing (+)")
            
        if volume_delta is not None:
            parts.append(f"Volume Delta Confirmed ({volume_delta})")

        parts.append(f"R:R = 1:{rr}")
        parts.append(f"Confluence Score: {confluence.total_score}/{confluence.max_score}")

        # --- Market Intelligence details (V4) ---
        if market_intel_data:
            mi = market_intel_data
            # BTC Dominance
            btc_dom = mi.get("btc_dominance", {})
            if btc_dom.get("btc_dominance", 0) > 0:
                dom_val = btc_dom["btc_dominance"]
                dom_trend = "falling" if btc_dom.get("market_cap_change_24h_pct", 0) < 0 else "rising"
                parts.append(f"BTC.D: {dom_val:.1f}% ({dom_trend})")

            # Order Book
            ob = mi.get("orderbook", {})
            if ob.get("buy_sell_ratio", 0) > 0:
                ratio = ob["buy_sell_ratio"]
                ob_label = "buy wall dominant" if ratio > 1.2 else "sell wall dominant" if ratio < 0.8 else "balanced"
                parts.append(f"Order Book: {ratio:.2f}x ({ob_label})")

            # Support & Resistance (V7: show snap info if S/R was used)
            sr = mi.get("support_resistance", {})
            nearest_s = sr.get("nearest_support", 0)
            nearest_r = sr.get("nearest_resistance", 0)
            if nearest_s > 0 or nearest_r > 0:
                sr_msg = f"S/R Reference — Support: {nearest_s:.4f} | Resistance: {nearest_r:.4f}"
                if direction == "BUY" and nearest_s > 0:
                    sr_msg += f" (Entry anchored near Support {nearest_s:.4f}; TP targets Resistance)"
                elif direction == "SELL" and nearest_r > 0:
                    sr_msg += f" (Entry anchored near Resistance {nearest_r:.4f}; TP targets Support)"
                parts.append(sr_msg)

            # Liquidation
            liq = mi.get("liquidation", {})
            cluster = liq.get("cluster_zone", {})
            if cluster.get("low", 0) > 0:
                parts.append(f"Liq. Cluster: {cluster['low']:.2f} - {cluster['high']:.2f}")

            # Market Cap
            mcap = mi.get("market_cap", {})
            tier = mcap.get("tier", "")
            if tier:
                parts.append(f"MCap: {tier}")

        return " | ".join(parts)

    def _build_setup_type(self, confluence: ConfluenceResult, direction: str) -> str:
        """Build setup type label."""
        parts = []
        details = confluence.details

        if details.get("liquidity", {}).get("swept"):
            parts.append("Liq Sweep")
        if details.get("order_block", {}).get("in_zone"):
            parts.append(f"{'Bullish' if direction == 'BUY' else 'Bearish'} OB")
        if details.get("fvg", {}).get("present"):
            parts.append("FVG")
        if details.get("premium_discount", {}).get("in_correct_zone"):
            parts.append("Discount" if direction == "BUY" else "Premium")

        return " + ".join(parts) if parts else "Multi-Confluence Setup"

    @staticmethod
    def _estimate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Estimate ATR from OHLCV data."""
        if df.empty or len(df) < 2:
            return 0.0
        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        closes = df["close"].astype(float).values

        trs = []
        for i in range(1, len(df)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)

        if not trs:
            return 0.0
        return sum(trs[-period:]) / min(period, len(trs))
