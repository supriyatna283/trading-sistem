import pandas as pd
import numpy as np
from typing import Optional, Tuple


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """
    Calculate the Relative Strength Index (RSI) for a given DataFrame.
    Returns the latest RSI value.
    """
    if len(df) < period + 1:
        return None

    closes = df["close"].astype(float).values
    deltas = np.diff(closes)

    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.zeros_like(gains)
    avg_loss = np.zeros_like(losses)

    avg_gain[period - 1] = np.mean(gains[:period])
    avg_loss[period - 1] = np.mean(losses[:period])

    for i in range(period, len(gains)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period

    latest_gain = avg_gain[-1]
    latest_loss = avg_loss[-1]

    if latest_loss == 0:
        return 100.0 if latest_gain > 0 else 50.0

    rs = latest_gain / latest_loss
    rsi = 100 - (100 / (1 + rs))

    return round(float(rsi), 2)


def calculate_ema(df: pd.DataFrame, period: int = 200) -> Optional[float]:
    """Calculate Exponential Moving Average."""
    if df.empty or len(df) < period:
        return None

    closes = df["close"].astype(float)
    ema = closes.ewm(span=period, adjust=False).mean()
    return round(float(ema.iloc[-1]), 4)


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
    """Calculate MACD. Returns (macd_line, signal_line, histogram)"""
    if df.empty or len(df) < slow + signal:
        return None, None, None

    closes = df["close"].astype(float)
    fast_ema = closes.ewm(span=fast, adjust=False).mean()
    slow_ema = closes.ewm(span=slow, adjust=False).mean()

    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return (
        round(float(macd_line.iloc[-1]), 6),
        round(float(signal_line.iloc[-1]), 6),
        round(float(histogram.iloc[-1]), 6),
    )


def calculate_bollinger_bands(
    df: pd.DataFrame, period: int = 20, std_dev: float = 2.0
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Calculate Bollinger Bands for intraday volatility analysis.
    Returns (upper_band, middle_band, lower_band, bandwidth_pct)
    - bandwidth_pct: squeeze indicator — narrow bands precede breakouts
    - Price at lower band = potential BUY zone
    - Price at upper band = potential SELL/exit zone
    """
    if df.empty or len(df) < period:
        return None, None, None, None

    closes = df["close"].astype(float)
    middle = closes.rolling(period).mean()
    std = closes.rolling(period).std()

    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    last_upper = float(upper.iloc[-1])
    last_middle = float(middle.iloc[-1])
    last_lower = float(lower.iloc[-1])

    # Bandwidth % = (Upper - Lower) / Middle * 100 (squeeze when < 5%)
    bandwidth_pct = (
        round((last_upper - last_lower) / last_middle * 100, 2)
        if last_middle != 0
        else None
    )

    return (
        round(last_upper, 4),
        round(last_middle, 4),
        round(last_lower, 4),
        bandwidth_pct,
    )


def calculate_stoch_rsi(
    df: pd.DataFrame,
    rsi_period: int = 14,
    stoch_period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculate Stochastic RSI — key intraday momentum timing tool.
    Returns (%K, %D) values between 0 and 100.
    - %K < 20 = oversold momentum → BUY signal
    - %K > 80 = overbought momentum → SELL signal
    - %K crossing above %D = bullish momentum crossover
    - %K crossing below %D = bearish momentum crossover
    """
    min_required = rsi_period + stoch_period + smooth_k + smooth_d + 10
    if df.empty or len(df) < min_required:
        return None, None

    closes = df["close"].astype(float)
    deltas = closes.diff()

    gains = deltas.clip(lower=0)
    losses = (-deltas).clip(lower=0)

    avg_gain = gains.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()
    avg_loss = losses.ewm(com=rsi_period - 1, min_periods=rsi_period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    rsi_series = rsi_series.dropna()

    if len(rsi_series) < stoch_period:
        return None, None

    rsi_min = rsi_series.rolling(stoch_period).min()
    rsi_max = rsi_series.rolling(stoch_period).max()

    stoch_raw = (rsi_series - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan) * 100

    k = stoch_raw.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()

    last_k = k.iloc[-1]
    last_d = d.iloc[-1]

    if pd.isna(last_k) or pd.isna(last_d):
        return None, None

    return round(float(last_k), 2), round(float(last_d), 2)
