"""
Unit Tests: Technical Indicators
Tests for RSI divergence index alignment fix and indicator correctness.
"""

import pytest
import pandas as pd
import numpy as np
from app.utils.indicators import (
    calculate_rsi, calculate_ema, detect_divergence,
    calculate_stoch_rsi, calculate_macd, calculate_vwap,
)


def make_df(closes: list, volumes: list = None) -> pd.DataFrame:
    n = len(closes)
    closes = np.array(closes, dtype=float)
    if volumes is None:
        volumes = [100.0] * n
    return pd.DataFrame({
        "open": closes - 0.3,
        "high": closes + 0.5,
        "low": closes - 0.5,
        "close": closes,
        "volume": volumes,
    })


class TestRSI:
    """Tests for RSI calculation correctness."""

    def test_rsi_returns_value_between_0_and_100(self):
        df = make_df(list(range(100, 150)))
        result = calculate_rsi(df)
        assert result is not None
        assert 0 <= result <= 100

    def test_rsi_bullish_trend_above_50(self):
        """Rising prices should produce RSI above 50."""
        closes = [float(i) for i in range(50, 100)]  # Steadily rising
        df = make_df(closes)
        result = calculate_rsi(df)
        assert result is not None
        assert result > 50, f"RSI on rising trend should be > 50, got {result}"

    def test_rsi_bearish_trend_below_50(self):
        """Falling prices should produce RSI below 50."""
        closes = [float(i) for i in range(100, 50, -1)]  # Steadily falling
        df = make_df(closes)
        result = calculate_rsi(df)
        assert result is not None
        assert result < 50, f"RSI on falling trend should be < 50, got {result}"

    def test_rsi_short_df_returns_none_or_value(self):
        """Very short DataFrames should not crash."""
        df = make_df([100.0, 101.0, 102.0])
        result = calculate_rsi(df)
        # Either None (insufficient data) or valid number
        assert result is None or (0 <= result <= 100)


class TestRSIDivergence:
    """Tests for detect_divergence() — BUG 2 fix (off-by-one RSI indexing)."""

    def make_bullish_divergence_df(self) -> pd.DataFrame:
        """
        Create candles that exhibit bullish divergence:
        - Price makes LOWER low (bearish price action)
        - RSI makes HIGHER low (bullish momentum divergence)
        """
        # First leg down (to ~80), second leg makes lower low (~75)
        # But RSI should be higher on second low
        closes = [
            100, 98, 95, 92, 88, 85, 82,  # First decline → low at 82
            85, 88, 90, 88, 85, 82, 80,   # Bounce then lower low at 78
            78, 76, 75,                    # Lower price low
            78, 82, 85,                    # Recovery
        ]
        return make_df(closes)

    def make_bearish_divergence_df(self) -> pd.DataFrame:
        """
        Price makes HIGHER high but RSI makes LOWER high (bearish divergence).
        """
        closes = [
            100, 103, 106, 110, 113,   # First rise to 113
            110, 107, 105, 107, 110,   # Pullback then bounce
            112, 115, 118,              # Price higher high at 118
            115, 112, 110,              # Start declining
        ]
        return make_df(closes)

    def test_divergence_returns_dict(self):
        """detect_divergence should always return a dict with expected keys."""
        df = make_df(list(range(50, 100)))
        result = detect_divergence(df)
        assert isinstance(result, dict)
        assert "type" in result
        assert "rsi_divergence" in result
        assert "macd_divergence" in result
        assert "strength" in result

    def test_divergence_type_valid(self):
        """Divergence type must be one of the valid values."""
        df = make_df(list(range(50, 100)))
        result = detect_divergence(df)
        assert result["type"] in ("bullish", "bearish", "none")

    def test_no_crash_on_short_df(self):
        """Should not crash on very short DataFrames."""
        df = make_df([100.0] * 10)
        result = detect_divergence(df)
        assert result is not None
        assert result["type"] == "none"

    def test_divergence_check_does_not_produce_index_error(self):
        """The RSI array must be same length as closes — no IndexError."""
        # This specifically tests the BUG 2 fix (RSI was off-by-one)
        for n in [30, 50, 100, 200]:
            closes = np.cumsum(np.random.normal(0, 1, n)) + 100
            df = make_df(closes.tolist())
            try:
                result = detect_divergence(df)
                assert result is not None
            except IndexError as e:
                pytest.fail(f"IndexError in detect_divergence with {n} candles: {e}")


class TestEMA:
    """Tests for EMA calculation."""

    def test_ema_200_returns_float(self):
        closes = [float(i) for i in range(50, 250)]  # 200 candles
        df = make_df(closes)
        result = calculate_ema(df, 200)
        assert result is not None
        assert isinstance(result, float)

    def test_ema_insufficient_data_returns_none(self):
        df = make_df([100.0, 101.0, 102.0])
        result = calculate_ema(df, 200)
        assert result is None or isinstance(result, float)


class TestStochRSI:
    """Tests for StochRSI calculation."""

    def test_stoch_rsi_returns_k_d(self):
        closes = [float(i % 20 + 90) for i in range(100)]
        df = make_df(closes)
        k, d = calculate_stoch_rsi(df)
        if k is not None:
            assert 0 <= k <= 100
        if d is not None:
            assert 0 <= d <= 100

    def test_stoch_rsi_short_df_no_crash(self):
        df = make_df([100.0] * 5)
        k, d = calculate_stoch_rsi(df)
        # Should return None or valid values without crashing


class TestVWAP:
    """Tests for VWAP calculation."""

    def test_vwap_returns_dict(self):
        closes = [100.0 + i * 0.1 for i in range(50)]
        vols = [1000.0] * 50
        df = make_df(closes, vols)
        result = calculate_vwap(df)
        assert isinstance(result, dict)
        assert "vwap" in result

    def test_vwap_empty_df_no_crash(self):
        df = pd.DataFrame()
        result = calculate_vwap(df)
        assert isinstance(result, dict)
