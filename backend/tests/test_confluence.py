"""
Unit Tests: Confluence Engine
Tests for V4 audit fixes: StochRSI thresholds, EMA tolerance, volume baseline, session.
"""

import pytest
import pandas as pd
import numpy as np
from app.engines.confluence import ConfluenceEngine


@pytest.fixture
def ce():
    return ConfluenceEngine()


class TestStochRSIThresholds:
    """Tests for _check_stoch_rsi_aligned() — BUG 5 fix."""

    def test_bullish_ideal_zone_passes(self, ce):
        """k=35 (rising from oversold, not extended) should pass for BULLISH."""
        assert ce._check_stoch_rsi_aligned(35, 30, "BULLISH") is True

    def test_bullish_too_high_rejected(self, ce):
        """k=58 (already elevated) should be rejected for BULLISH entry."""
        assert ce._check_stoch_rsi_aligned(58, 50, "BULLISH") is False

    def test_bullish_extreme_oversold_rejected(self, ce):
        """k=10 (extreme oversold, below 20) should be rejected — too early, not turning yet."""
        assert ce._check_stoch_rsi_aligned(10, 8, "BULLISH") is False

    def test_bullish_requires_k_above_d(self, ce):
        """k must be above d for BULLISH momentum confirmation."""
        # k=35, d=40 → k is below d → not confirmed
        assert ce._check_stoch_rsi_aligned(35, 40, "BULLISH") is False

    def test_bearish_ideal_zone_passes(self, ce):
        """k=65 (falling from overbought, not extreme) should pass for BEARISH."""
        assert ce._check_stoch_rsi_aligned(65, 70, "BEARISH") is True

    def test_bearish_too_low_rejected(self, ce):
        """k=42 (already in oversold territory) should be rejected for BEARISH entry."""
        assert ce._check_stoch_rsi_aligned(42, 38, "BEARISH") is False

    def test_bearish_extreme_overbought_rejected(self, ce):
        """k=88 (extreme overbought, above 80) should be rejected — too early."""
        assert ce._check_stoch_rsi_aligned(88, 85, "BEARISH") is False


class TestEMATolerance:
    """Tests for _check_ema_aligned() — BUG 7 fix (tolerance 8% → 3%)."""

    def test_price_above_ema_bullish_passes(self, ce):
        df = pd.DataFrame({"close": [103.0]})
        assert ce._check_ema_aligned(df, 100.0, "BULLISH") is True

    def test_price_within_3pct_below_ema_bullish_passes(self, ce):
        """2.5% below EMA200 is a valid re-test pullback — should pass."""
        df = pd.DataFrame({"close": [97.5]})
        assert ce._check_ema_aligned(df, 100.0, "BULLISH") is True

    def test_price_beyond_3pct_below_ema_bullish_fails(self, ce):
        """9% below EMA200 is deep bearish territory — should fail."""
        df = pd.DataFrame({"close": [91.0]})
        assert ce._check_ema_aligned(df, 100.0, "BULLISH") is False

    def test_price_below_ema_bearish_passes(self, ce):
        df = pd.DataFrame({"close": [97.0]})
        assert ce._check_ema_aligned(df, 100.0, "BEARISH") is True

    def test_price_within_3pct_above_ema_bearish_passes(self, ce):
        """2.5% above EMA200 is a valid re-test — should pass for BEARISH."""
        df = pd.DataFrame({"close": [102.5]})
        assert ce._check_ema_aligned(df, 100.0, "BEARISH") is True

    def test_price_beyond_3pct_above_ema_bearish_fails(self, ce):
        df = pd.DataFrame({"close": [110.0]})
        assert ce._check_ema_aligned(df, 100.0, "BEARISH") is False


class TestVolumeBaseline:
    """Tests for _check_volume_confirmation() — BUG 8 fix (mean → median)."""

    def make_df_with_volume(self, volumes: list, symbol: str = "ALTUSDT") -> pd.DataFrame:
        n = len(volumes)
        return pd.DataFrame({
            "open": [100.0] * n,
            "high": [101.0] * n,
            "low": [99.0] * n,
            "close": [100.0] * n,
            "volume": volumes,
        })

    def test_spike_does_not_inflate_baseline(self, ce):
        """A historical spike should NOT inflate the median baseline."""
        volumes = [100.0] * 20 + [5000.0] + [100.0] * 28 + [150.0]
        df = self.make_df_with_volume(volumes)
        result = ce._check_volume_confirmation(df, "ALTUSDT")
        # With median ~100 and threshold 2.0x, need vol>=200, so 150 should fail
        assert bool(result) is False, "Volume 150 vs median 100 (2.0x threshold) should fail"

    def test_genuine_spike_passes(self, ce):
        """A genuine 2.1x volume spike above median should pass."""
        volumes = [100.0] * 49 + [210.0]
        df = self.make_df_with_volume(volumes)
        result = ce._check_volume_confirmation(df, "ALTUSDT")
        assert bool(result) is True, "Volume 210 vs median 100 (2.0x threshold) should pass"

    def test_btc_lower_threshold(self, ce):
        """BTC uses 1.5x threshold (more liquid), so lower spike is sufficient."""
        volumes = [100.0] * 49 + [160.0]
        df = self.make_df_with_volume(volumes)
        result = ce._check_volume_confirmation(df, "BTCUSDT")
        assert bool(result) is True, "BTC volume 160 vs median 100 (1.5x threshold) should pass"


class TestSessionWeighting:
    """Tests for _get_session_score() — item #11 Liquid Session Weighting."""

    def make_df_with_hour(self, hour: int) -> pd.DataFrame:
        ts = pd.Timestamp(f"2025-01-13 {hour:02d}:00:00")
        return pd.DataFrame({
            "open": [100.0], "high": [101.0], "low": [99.0],
            "close": [100.0], "volume": [100.0], "open_time": [ts],
        })

    def test_dead_hours_penalty(self, ce):
        """Hour 03 UTC should give -3 penalty (dead hours)."""
        df = self.make_df_with_hour(3)
        assert ce._get_session_score(df) == -3

    def test_prime_london_open(self, ce):
        """Hour 08 UTC (London Open) should give +2 bonus."""
        df = self.make_df_with_hour(8)
        assert ce._get_session_score(df) == 2

    def test_prime_ny_open(self, ce):
        """Hour 13 UTC (NY Open) should give +2 bonus."""
        df = self.make_df_with_hour(13)
        assert ce._get_session_score(df) == 2

    def test_active_session(self, ce):
        """Hour 11 UTC (London active, not prime) should give +1."""
        df = self.make_df_with_hour(11)
        assert ce._get_session_score(df) == 1

    def test_asian_session_neutral(self, ce):
        """Hour 06 UTC (Asian session) should give 0 (neutral)."""
        df = self.make_df_with_hour(6)
        assert ce._get_session_score(df) == 0

    def test_no_timestamp_neutral(self, ce):
        """DataFrame without open_time should give 0 (not penalized)."""
        df = pd.DataFrame({
            "open": [100.0], "high": [101.0], "low": [99.0],
            "close": [100.0], "volume": [100.0],
        })
        assert ce._get_session_score(df) == 0

    def test_min_score_threshold(self, ce):
        """ConfluenceEngine should have min_score of 18."""
        assert ce.min_confluence_score == 18
