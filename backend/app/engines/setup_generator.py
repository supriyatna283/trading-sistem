"""
Trading Setup Generator (V4 - Market Intelligence Enriched)
==============================================================
Generates trade ideas based on SMC, Confluence, and Market Intelligence.
- Minimum confluence score: 5/24 (standard logic)
- Minimum R:R ratio: 1.5
- Uses S/R levels to refine entry/SL/TP.
- Enriches signal explanation with market intel details.
"""

import pandas as pd
from typing import Optional, List, Dict
from app.schemas.trade_setup import TradeSetupSchema, ConfluenceResult
from app.schemas.market_data import SmartMoneyAnalysis, MarketBias


class SetupGenerator:
    """V3 — Generates actionable trading setups."""

    def __init__(self, min_confluence_score: int = 5, min_rr: float = 1.5):
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
    ) -> Optional[TradeSetupSchema]:
        """Generate a setup ONLY if ALL quality gates pass."""

        # ---- Quality Gate 1: Minimum Confluence Score ----
        if confluence.total_score < self.min_score:
            return None

        # ---- Quality Gate 2: Must have a clear direction ----
        if confluence.recommendation in ("NEUTRAL",):
            return None

        if df.empty or len(df) < 20:
            return None

        direction = "BUY" if confluence.recommendation in ("BUY", "STRONG_BUY") else "SELL"

        # ---- Quality Gate 3: HTF bias must agree with direction ----
        htf_details = confluence.details.get("htf_bias", {})
        if htf_details.get("aligned"):
            htf_biases = htf_details.get("biases", {})
            dominant_bias = list(htf_biases.values())[0] if htf_biases else "SIDEWAYS"
            if direction == "BUY" and dominant_bias != "BULLISH":
                return None
            if direction == "SELL" and dominant_bias != "BEARISH":
                return None

        last_price = float(df.iloc[-1]["close"])
        entry_low, entry_high, sl, tp1, tp2, tp3 = self._calculate_levels(
            direction, last_price, smc, df
        )

        risk = abs(entry_low - sl) if direction == "BUY" else abs(sl - entry_high)
        reward = abs(tp1 - entry_high) if direction == "BUY" else abs(entry_low - tp1)
        rr = round(reward / risk, 2) if risk > 0 else 0

        if rr < self.min_rr:
            return None

        # ---- Quality Gate 5: Stop loss sanity check ----
        major_pairs = {"BTCUSDT", "ETHUSDT", "BNBUSDT"}
        max_sl_pct = 3.0 if symbol.upper() in major_pairs else 5.0
        sl_distance_pct = abs(sl - last_price) / last_price * 100
        if sl_distance_pct > max_sl_pct:
            return None

        # Macro filters (MTF, News, Sentiment) are now considered inside the confluence score
        # rather than being strict blockers, to maximize signal generation based on core technicals.

        # Build detailed explanation (V4 — includes market intel)
        explanation = self._build_explanation(confluence, direction, rr, market_intel_data)
        setup_type = self._build_setup_type(confluence, direction)

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
        smc: SmartMoneyAnalysis, df: pd.DataFrame
    ):
        """Calculate precise entry, SL, and TP levels using OB zones + ATR."""
        recent = df.tail(20)
        atr = self._estimate_atr(recent)

        if direction == "BUY":
            # Entry at the nearest valid (unmitigated) bullish OB
            bullish_obs = [ob for ob in smc.order_blocks
                          if ob.type == "BULLISH" and not ob.mitigated]
            if bullish_obs:
                ob = bullish_obs[-1]
                entry_low = ob.low
                entry_high = ob.high
            else:
                entry_low = last_price - atr * 0.3
                entry_high = last_price

            # SL: 1 ATR below OB low
            sl = entry_low - atr * 1.0

            # TP: Use ATR multiples for R:R-based targets
            risk = entry_low - sl
            tp1 = entry_high + risk * 1.6    # Target 1.5+ comfortably
            tp2 = entry_high + risk * 3.0
            tp3 = entry_high + risk * 5.0

        else:  # SELL
            bearish_obs = [ob for ob in smc.order_blocks
                          if ob.type == "BEARISH" and not ob.mitigated]
            if bearish_obs:
                ob = bearish_obs[-1]
                entry_low = ob.low
                entry_high = ob.high
            else:
                entry_low = last_price
                entry_high = last_price + atr * 0.3

            # SL: 1 ATR above OB high
            sl = entry_high + atr * 1.0

            risk = sl - entry_high
            tp1 = entry_low - risk * 1.6
            tp2 = entry_low - risk * 3.0
            tp3 = entry_low - risk * 5.0

        return entry_low, entry_high, sl, tp1, tp2, tp3

    def _build_explanation(self, confluence: ConfluenceResult, direction: str, rr: float, market_intel_data: Optional[Dict] = None) -> str:
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

            # Support & Resistance
            sr = mi.get("support_resistance", {})
            if sr.get("nearest_support", 0) > 0:
                parts.append(f"Support: {sr['nearest_support']:.2f} | Resistance: {sr.get('nearest_resistance', 0):.2f}")

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
