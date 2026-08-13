"""Shared pytest fixtures for all trading engine tests."""

import pytest
import pandas as pd
import numpy as np


def make_ohlcv(
    n: int = 200,
    trend: str = "bullish",
    base_price: float = 100.0,
    volatility: float = 0.5,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV candles.

    Args:
        n: Number of candles
        trend: 'bullish', 'bearish', or 'ranging'
        base_price: Starting price
        volatility: ATR-like noise in price units
        seed: Random seed for reproducibility
    """
    rng = np.random.default_rng(seed)

    closes = [base_price]
    for _ in range(n - 1):
        if trend == "bullish":
            drift = 0.05
        elif trend == "bearish":
            drift = -0.05
        else:
            drift = 0.0
        closes.append(closes[-1] + drift + rng.normal(0, volatility))

    closes = np.array(closes)
    highs = closes + rng.uniform(0.1, volatility * 1.5, n)
    lows = closes - rng.uniform(0.1, volatility * 1.5, n)
    opens = closes - rng.normal(0, volatility * 0.3, n)
    volumes = rng.uniform(100, 500, n)

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


@pytest.fixture
def sample_bullish_df():
    """200-candle bullish trending DataFrame."""
    return make_ohlcv(200, trend="bullish")


@pytest.fixture
def sample_bearish_df():
    """200-candle bearish trending DataFrame."""
    return make_ohlcv(200, trend="bearish")


@pytest.fixture
def sample_ranging_df():
    """200-candle ranging/sideways DataFrame."""
    return make_ohlcv(200, trend="ranging")


@pytest.fixture
def smc_engine():
    from app.engines.smart_money import SmartMoneyConceptsEngine
    return SmartMoneyConceptsEngine()


@pytest.fixture
def confluence_engine():
    from app.engines.confluence import ConfluenceEngine
    return ConfluenceEngine()


@pytest.fixture
def structure_analyzer():
    from app.engines.market_structure import MarketStructureAnalyzer
    return MarketStructureAnalyzer()
