import pandas as pd
import numpy as np
from typing import Optional

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
    
    # Use Exponential Moving Average (Wilder's smoothing) for RSI
    # Note: strategy_builder.py uses a simple mean, which is less accurate but common for quick checks.
    # We'll use the proper Wilder approach here.
    
    avg_gain = np.zeros_like(gains)
    avg_loss = np.zeros_like(losses)
    
    # Initial average
    avg_gain[period-1] = np.mean(gains[:period])
    avg_loss[period-1] = np.mean(losses[:period])
    
    # Wilder's Smoothing
    for i in range(period, len(gains)):
        avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i]) / period
        
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
        round(float(histogram.iloc[-1]), 6)
    )
