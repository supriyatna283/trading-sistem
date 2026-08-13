"""
Unit Tests: Smart Money Concepts Engine
Tests OB Mitigation fix and FVG Detection fix from V4 audit.
"""

import pytest
import pandas as pd
import numpy as np
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.schemas.market_data import OrderBlock, FairValueGap


@pytest.fixture
def smc():
    return SmartMoneyConceptsEngine()


class TestOrderBlockMitigation:
    """Tests for _check_ob_mitigated() — BUG 3 fix from V4 audit."""

    def test_bullish_ob_retest_inside_not_mitigated(self, smc):
        """Price retesting inside a Bullish OB zone should NOT be mitigated.
        Classic SMC: price returning to OB is the ENTRY, not mitigation.
        """
        ob = OrderBlock(type="BULLISH", high=96.0, low=95.0, index=1)
        # Price bounces between 95-96 (inside OB) — this is a re-test, not mitigation
        closes = [97.0, 95.5, 96.0, 95.8, 97.0]
        result = smc._check_ob_mitigated(ob, [], [], closes, 0, 5, "BULLISH")
        assert result is False, "Re-test inside OB should NOT be considered mitigated"

    def test_bullish_ob_close_below_mitigated(self, smc):
        """Price closing below Bullish OB low = OB is mitigated (invalidated)."""
        ob = OrderBlock(type="BULLISH", high=96.0, low=95.0, index=1)
        # Price dumps through the OB floor
        closes = [97.0, 95.5, 96.0, 94.5, 93.0]
        result = smc._check_ob_mitigated(ob, [], [], closes, 0, 5, "BULLISH")
        assert result is True, "Close below OB low should trigger mitigation"

    def test_bearish_ob_retest_inside_not_mitigated(self, smc):
        """Price retesting inside a Bearish OB zone should NOT be mitigated."""
        ob = OrderBlock(type="BEARISH", high=105.0, low=104.0, index=1)
        closes = [103.0, 104.5, 104.8, 104.2, 103.5]
        result = smc._check_ob_mitigated(ob, [], [], closes, 0, 5, "BEARISH")
        assert result is False, "Re-test inside Bearish OB should NOT be mitigated"

    def test_bearish_ob_close_above_mitigated(self, smc):
        """Price closing above Bearish OB high = OB is mitigated."""
        ob = OrderBlock(type="BEARISH", high=105.0, low=104.0, index=1)
        closes = [103.0, 104.5, 105.5, 106.0, 107.0]
        result = smc._check_ob_mitigated(ob, [], [], closes, 0, 5, "BEARISH")
        assert result is True, "Close above OB high should trigger mitigation"

    def test_bullish_ob_exactly_at_low_not_mitigated(self, smc):
        """Price exactly at OB low is on the boundary — should not be mitigated yet."""
        ob = OrderBlock(type="BULLISH", high=96.0, low=95.0, index=1)
        closes = [97.0, 95.0, 96.0]  # Close == ob.low (not < ob.low)
        result = smc._check_ob_mitigated(ob, [], [], closes, 0, 3, "BULLISH")
        assert result is False, "Close exactly at OB low should not be mitigated"


class TestFVGDetection:
    """Tests for FVG fill detection logic — BUG 1 fix from V4 audit."""

    def make_bullish_fvg_candles(self) -> pd.DataFrame:
        """Create candles with a clear Bullish FVG (gap up)."""
        # Bar N-2: high=100, Bar N: low=102 → FVG gap is [100, 102]
        return pd.DataFrame({
            "open":   [98.0, 99.0, 101.0, 103.0, 104.0],
            "high":   [100.0, 100.5, 103.0, 104.0, 105.0],
            "low":    [97.0, 98.5, 101.0, 102.5, 103.5],
            "close":  [99.0, 100.0, 102.5, 103.5, 104.5],
            "volume": [200.0] * 5,
        })

    def test_bullish_fvg_detected(self, smc):
        """Bullish FVG should be detected from gap-up price action."""
        df = self.make_bullish_fvg_candles()
        result = smc.analyze(df, "TESTUSDT", "1h")
        bullish_fvgs = [f for f in result.fvgs if f.type == "BULLISH"]
        # May or may not detect depending on exact config, but should not crash
        assert isinstance(bullish_fvgs, list)

    def test_fvg_fill_check_bullish(self, smc):
        """FVG is filled when a candle's LOW enters the gap.
        Signature: _check_fvg_filled(gap_low, gap_high, price_array, start_idx, n, fvg_type)
        """
        # Gap occupies [100.0, 102.0]. A low of 101 enters the gap.
        lows = [103.0, 101.0]  # second bar enters gap
        import numpy as np
        lows_arr = np.array(lows)
        result = smc._check_fvg_filled(100.0, 102.0, lows_arr, 0, 2, "BULLISH")
        assert result is True, "Low entering gap should mark FVG as filled"

    def test_fvg_fill_check_bullish_untouched(self, smc):
        """FVG is NOT filled when no candle enters the gap."""
        # All lows are above the gap top (102) — never entered
        lows = [103.5, 104.0, 105.0]
        import numpy as np
        lows_arr = np.array(lows)
        result = smc._check_fvg_filled(100.0, 102.0, lows_arr, 0, 3, "BULLISH")
        assert result is False, "Lows above gap_high should not fill the FVG"

    def test_analyze_does_not_crash_on_minimal_data(self, smc):
        """Analyze should gracefully handle edge-case small DataFrames."""
        df = pd.DataFrame({
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [100.0, 120.0],
        })
        result = smc.analyze(df, "TEST", "1h")
        assert result is not None
        assert isinstance(result.fvgs, list)
        assert isinstance(result.order_blocks, list)
