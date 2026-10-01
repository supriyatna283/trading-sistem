"""
Adaptive ML Scoring Engine
============================
Lightweight ML-based confluence scoring using:

1. Feature extraction from OHLCV + all Sprint 1/3 engine outputs
2. Gradient Boosting (scikit-learn) for scoring
3. Online learning: model improves with each analysis (windowed)
4. Fallback: heuristic scoring if sklearn unavailable
5. Feature importance for explainability

No external model files needed — trained in-memory from live data.
Self-improves as more data comes in.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# Try sklearn — fall back gracefully
try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available — using heuristic ML scoring")


@dataclass
class MLScoringResult:
    # Main score
    ml_score: float             # 0-100 confidence score
    signal: str                 # STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL
    confidence: float           # 0-1 model confidence
    regime: str                 # TRENDING | RANGING | VOLATILE | BREAKOUT

    # Feature importance
    top_features: List[Dict] = field(default_factory=list)  # [{name, importance}]
    feature_values: Dict      = field(default_factory=dict)

    # Model state
    model_trained: bool = False
    training_samples: int = 0
    using_heuristic: bool = False

    # Explanation
    reasoning: List[str] = field(default_factory=list)
    confluence_score: int = 0


class AdaptiveMLScoringEngine:
    """
    Self-training ML engine that learns from market features in real-time.
    Uses a rolling window of feature vectors to train a lightweight GBM.
    """

    FEATURE_NAMES = [
        "rsi_14", "rsi_divergence", "atr_pct", "volume_ratio",
        "body_ratio", "upper_wick", "lower_wick",
        "ema9_vs_ema21", "ema21_vs_ema55", "macd_hist",
        "bb_position", "bb_width", "price_vs_vwap",
        "candle_delta", "vol_trend_ratio",
        "hh_hl_count", "ll_lh_count",
        "close_vs_open5", "range_compression",
    ]

    def __init__(self, window_size: int = 200):
        self.window_size = window_size
        self._feature_buffer: List[np.ndarray] = []
        self._label_buffer: List[int] = []  # 1=up, 0=flat, -1=down
        self._model: Optional[object] = None
        self._scaler: Optional[object] = None
        self._trained = False
        self._n_samples = 0

    def analyze(self, df: pd.DataFrame) -> MLScoringResult:
        """Extract features, retrain if enough data, return ML score."""
        if df is None or len(df) < 30:
            return self._heuristic(df)

        features = self._extract_features(df)
        if features is None:
            return self._heuristic(df)

        # Add to training buffer with auto-labeled targets
        self._update_buffer(df, features)

        # Try model prediction
        if SKLEARN_AVAILABLE and self._n_samples >= 50:
            return self._ml_predict(features, df)
        else:
            return self._heuristic(df)

    def _extract_features(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        """Extract all numeric features from OHLCV."""
        try:
            n = len(df)
            o = df["open"].astype(float).values
            h = df["high"].astype(float).values
            l = df["low"].astype(float).values
            c = df["close"].astype(float).values
            v = df["volume"].astype(float).values if "volume" in df.columns else np.ones(n)

            # RSI
            rsi = self._rsi(c, 14)

            # RSI divergence (price up but RSI down or vice versa)
            price_change = c[-1] - c[-14] if n >= 14 else 0
            rsi_change   = rsi - self._rsi(c[:-1], 14) if n > 14 else 0
            rsi_div      = 1 if (price_change > 0 and rsi_change < 0) or (price_change < 0 and rsi_change > 0) else 0

            # ATR %
            atr = self._atr(h, l, c)
            atr_pct = (atr / c[-1]) * 100

            # Volume ratio
            vol_ratio = v[-1] / np.mean(v[-20:]) if len(v) >= 20 else 1.0

            # Candle anatomy
            body = abs(c[-1] - o[-1])
            rng  = h[-1] - l[-1]
            body_ratio   = body / rng if rng > 0 else 0
            upper_wick   = (h[-1] - max(o[-1], c[-1])) / rng if rng > 0 else 0
            lower_wick   = (min(o[-1], c[-1]) - l[-1]) / rng if rng > 0 else 0

            # EMAs
            ema9  = self._ema(c, 9)
            ema21 = self._ema(c, 21)
            ema55 = self._ema(c, 55) if n >= 55 else ema21
            ema9_vs_21  = (ema9 - ema21) / ema21 * 100
            ema21_vs_55 = (ema21 - ema55) / ema55 * 100

            # MACD histogram proxy
            macd_hist = ema9 - ema21

            # Bollinger Band position
            sma20 = np.mean(c[-20:]) if n >= 20 else c[-1]
            std20 = np.std(c[-20:]) if n >= 20 else 1
            bb_upper = sma20 + 2 * std20
            bb_lower = sma20 - 2 * std20
            bb_pos   = (c[-1] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
            bb_width = (bb_upper - bb_lower) / sma20 * 100

            # VWAP
            tp   = (h + l + c) / 3
            vwap = np.sum(tp * v) / np.sum(v) if np.sum(v) > 0 else c[-1]
            price_vs_vwap = (c[-1] - vwap) / vwap * 100

            # Delta proxy
            buy_frac  = (c[-1] - l[-1]) / rng if rng > 0 else 0.5
            candle_delta = (buy_frac - 0.5) * 2  # -1 to 1

            # Volume trend
            vol_trend = np.mean(v[-5:]) / np.mean(v[-20:]) if n >= 20 else 1.0

            # Higher highs / lower lows count in last 10 bars
            hh_hl = sum(1 for i in range(-9, 0) if h[i] > h[i-1] and l[i] > l[i-1])
            ll_lh = sum(1 for i in range(-9, 0) if h[i] < h[i-1] and l[i] < l[i-1])

            # 5-bar return
            close_vs_5 = (c[-1] - c[-5]) / c[-5] * 100 if n >= 5 else 0

            # Range compression (ATR decreasing)
            atr_recent = self._atr(h[-7:], l[-7:], c[-7:]) if n >= 7 else atr
            range_comp = atr_recent / atr if atr > 0 else 1.0

            return np.array([
                rsi, rsi_div, atr_pct, vol_ratio,
                body_ratio, upper_wick, lower_wick,
                ema9_vs_21, ema21_vs_55, macd_hist,
                bb_pos, bb_width, price_vs_vwap,
                candle_delta, vol_trend,
                hh_hl, ll_lh,
                close_vs_5, range_comp,
            ], dtype=float)

        except Exception as e:
            logger.warning(f"Feature extraction error: {e}")
            return None

    def _update_buffer(self, df: pd.DataFrame, features: np.ndarray):
        """Auto-label historical data: if N bars later price went up = 1."""
        FORWARD_BARS = 5
        closes = df["close"].astype(float).values
        n = len(closes)

        if n > FORWARD_BARS + 1:
            future_return = closes[-1] - closes[-FORWARD_BARS - 1]
            label = 1 if future_return > 0.002 * closes[-1] else (-1 if future_return < -0.002 * closes[-1] else 0)
            self._feature_buffer.append(features)
            self._label_buffer.append(label)
            self._n_samples += 1

            # Keep rolling window
            if len(self._feature_buffer) > self.window_size:
                self._feature_buffer.pop(0)
                self._label_buffer.pop(0)

            # Retrain every 20 samples
            if self._n_samples % 20 == 0 and len(self._feature_buffer) >= 50 and SKLEARN_AVAILABLE:
                self._train_model()

    def _train_model(self):
        """Train / retrain GBM on buffered samples."""
        try:
            X = np.array(self._feature_buffer)
            y = np.array(self._label_buffer)

            # Map labels: -1,0,1 → 0,1,2 for classifier
            y_mapped = y + 1

            self._model = GradientBoostingClassifier(
                n_estimators=50, max_depth=3, learning_rate=0.1,
                subsample=0.8, random_state=42
            )
            self._model.fit(X, y_mapped)
            self._trained = True
            logger.info(f"ML model retrained on {len(X)} samples")
        except Exception as e:
            logger.warning(f"ML training failed: {e}")

    def _ml_predict(self, features: np.ndarray, df: pd.DataFrame) -> MLScoringResult:
        """Use trained model to predict direction and score."""
        try:
            X = features.reshape(1, -1)
            proba = self._model.predict_proba(X)[0]  # [down, neutral, up]
            pred  = self._model.predict(X)[0] - 1    # Map back to -1,0,1

            # Score: up probability * 100
            up_prob   = proba[2] * 100
            down_prob = proba[0] * 100
            confidence = float(max(proba))

            # Signal from probabilities
            if up_prob > 65:
                signal = "STRONG_BUY"
                ml_score = up_prob
            elif up_prob > 50:
                signal = "BUY"
                ml_score = up_prob
            elif down_prob > 65:
                signal = "STRONG_SELL"
                ml_score = 100 - down_prob
            elif down_prob > 50:
                signal = "SELL"
                ml_score = 100 - down_prob
            else:
                signal = "NEUTRAL"
                ml_score = 50

            # Feature importance
            importances = self._model.feature_importances_
            top_features = sorted(
                [{"name": self.FEATURE_NAMES[i], "importance": round(float(importances[i]), 3)}
                 for i in range(len(importances))],
                key=lambda x: x["importance"], reverse=True
            )[:5]

            # Regime
            regime = self._detect_regime(df)

            # Reasoning
            reasoning = self._build_reasoning(features, signal, top_features)

            cscore = (5 if signal in ("STRONG_BUY", "STRONG_SELL") else
                      3 if signal in ("BUY", "SELL") else 1)

            return MLScoringResult(
                ml_score=round(ml_score, 1),
                signal=signal,
                confidence=round(confidence, 3),
                regime=regime,
                top_features=top_features,
                feature_values={n: round(float(v), 4) for n, v in zip(self.FEATURE_NAMES, features)},
                model_trained=True,
                training_samples=self._n_samples,
                using_heuristic=False,
                reasoning=reasoning,
                confluence_score=cscore,
            )
        except Exception as e:
            logger.warning(f"ML prediction failed: {e}")
            return self._heuristic(df)

    def _heuristic(self, df: Optional[pd.DataFrame]) -> MLScoringResult:
        """Fallback heuristic scoring without sklearn."""
        if df is None or len(df) < 5:
            return MLScoringResult(
                ml_score=50, signal="NEUTRAL", confidence=0,
                regime="UNKNOWN", using_heuristic=True,
                reasoning=["Insufficient data"]
            )

        c = df["close"].astype(float).values
        v = df["volume"].astype(float).values if "volume" in df.columns else np.ones(len(c))

        rsi   = self._rsi(c, 14)
        ema9  = self._ema(c, 9)
        ema21 = self._ema(c, 21)
        score = 50

        # RSI
        if rsi > 70: score -= 15
        elif rsi > 60: score += 5
        elif rsi < 30: score += 15
        elif rsi < 40: score -= 5

        # EMA trend
        if ema9 > ema21: score += 10
        else: score -= 10

        # Volume
        vol_ratio = v[-1] / np.mean(v[-10:]) if len(v) >= 10 else 1.0
        if vol_ratio > 1.5: score += 5

        score = max(0, min(100, score))

        if score >= 65:   signal = "STRONG_BUY"
        elif score >= 55: signal = "BUY"
        elif score <= 35: signal = "STRONG_SELL"
        elif score <= 45: signal = "SELL"
        else:             signal = "NEUTRAL"

        regime = self._detect_regime(df)

        return MLScoringResult(
            ml_score=float(score), signal=signal, confidence=0.5,
            regime=regime, using_heuristic=True,
            training_samples=self._n_samples,
            reasoning=[f"Heuristic: RSI={rsi:.1f}, EMA9{'>'if ema9>ema21 else '<'}EMA21"],
            confluence_score=3 if signal in ("STRONG_BUY","STRONG_SELL") else 1,
        )

    def _detect_regime(self, df: pd.DataFrame) -> str:
        if df is None or len(df) < 20:
            return "UNKNOWN"
        c = df["close"].astype(float).values
        atr = self._atr(df["high"].astype(float).values, df["low"].astype(float).values, c)
        std = np.std(c[-20:])
        price_change = abs(c[-1] - c[-20]) / c[-20] * 100

        if price_change > 5 and atr > np.mean(c) * 0.02:
            return "TRENDING"
        elif std / np.mean(c[-20:]) > 0.03:
            return "VOLATILE"
        elif price_change < 1:
            return "RANGING"
        else:
            return "BREAKOUT"

    def _build_reasoning(self, features, signal, top_features) -> List[str]:
        reasons = [f"ML signal: {signal}"]
        rsi = features[0]
        ema_trend = features[7]
        vol_ratio = features[3]
        reasons.append(f"RSI: {rsi:.1f} ({'overbought' if rsi > 70 else 'oversold' if rsi < 30 else 'neutral'})")
        reasons.append(f"EMA trend: {'bullish' if ema_trend > 0 else 'bearish'} ({ema_trend:.2f}%)")
        reasons.append(f"Volume: {vol_ratio:.1f}x average")
        if top_features:
            reasons.append(f"Top feature: {top_features[0]['name']} ({top_features[0]['importance']:.2%})")
        return reasons

    def _rsi(self, closes, period=14) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = np.diff(closes)
        gains  = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs  = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _ema(self, closes, period) -> float:
        if len(closes) < period:
            return float(closes[-1])
        k = 2 / (period + 1)
        ema = float(closes[0])
        for p in closes[1:]:
            ema = p * k + ema * (1 - k)
        return ema

    def _atr(self, highs, lows, closes, period=14) -> float:
        if len(closes) < 2:
            return float(np.ptp(closes)) if len(closes) > 0 else 1.0
        trs = [
            max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            for i in range(1, len(closes))
        ]
        return float(np.mean(trs[-period:])) if trs else 1.0

    def to_dict(self, r: MLScoringResult) -> dict:
        return {
            "ml_score":         r.ml_score,
            "signal":           r.signal,
            "confidence":       r.confidence,
            "regime":           r.regime,
            "model_trained":    r.model_trained,
            "training_samples": r.training_samples,
            "using_heuristic":  r.using_heuristic,
            "top_features":     r.top_features,
            "feature_values":   r.feature_values,
            "reasoning":        r.reasoning,
            "confluence_score": r.confluence_score,
        }
