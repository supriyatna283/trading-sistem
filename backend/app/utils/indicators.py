import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict


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
    Calculate Stochastic RSI.
    Returns (%K, %D) values between 0 and 100.
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


# ══════════════════════════════════════════════════════════════════
# TIER 1 — NEW INDICATORS
# ══════════════════════════════════════════════════════════════════

def calculate_vwap(df: pd.DataFrame) -> Dict:
    """
    Calculate VWAP (Volume Weighted Average Price).
    VWAP = Σ(Typical Price × Volume) / Σ(Volume)
    - Price above VWAP = bullish institutional bias
    - Price below VWAP = bearish institutional bias
    Returns: {vwap, position ('above'/'below'), distance_pct}
    """
    if df.empty or len(df) < 5 or "volume" not in df.columns:
        return {"vwap": None, "position": None, "distance_pct": None}

    try:
        df = df.copy()
        df["typical_price"] = (
            df["high"].astype(float) + df["low"].astype(float) + df["close"].astype(float)
        ) / 3
        df["vol"] = df["volume"].astype(float)
        df["tp_vol"] = df["typical_price"] * df["vol"]

        window = df.tail(100)
        cum_tp_vol = window["tp_vol"].sum()
        cum_vol = window["vol"].sum()

        if cum_vol == 0:
            return {"vwap": None, "position": None, "distance_pct": None}

        vwap = cum_tp_vol / cum_vol
        last_close = float(df["close"].iloc[-1])
        position = "above" if last_close > vwap else "below"
        distance_pct = round(abs(last_close - vwap) / vwap * 100, 3)

        return {
            "vwap": round(float(vwap), 4),
            "position": position,
            "distance_pct": distance_pct,
        }
    except Exception:
        return {"vwap": None, "position": None, "distance_pct": None}


def calculate_volume_profile(df: pd.DataFrame, bins: int = 20) -> Dict:
    """
    Calculate Volume Profile — Point of Control (POC), Value Area High/Low.
    - POC = price level with highest volume → strongest S/R
    - VAH/VAL = bounds of top 70% of traded volume
    Returns: {poc, vah, val, poc_distance_pct, in_value_area}
    """
    if df.empty or len(df) < 20 or "volume" not in df.columns:
        return {"poc": None, "vah": None, "val": None, "poc_distance_pct": None, "in_value_area": False}

    try:
        highs = df["high"].astype(float)
        lows = df["low"].astype(float)
        closes = df["close"].astype(float)
        volumes = df["volume"].astype(float)

        price_min = lows.min()
        price_max = highs.max()
        bin_size = (price_max - price_min) / bins

        if bin_size == 0:
            return {"poc": None, "vah": None, "val": None, "poc_distance_pct": None, "in_value_area": False}

        volume_at_price = np.zeros(bins)
        bin_edges = np.linspace(price_min, price_max, bins + 1)

        for i in range(len(df)):
            low_i = float(lows.iloc[i])
            high_i = float(highs.iloc[i])
            vol_i = float(volumes.iloc[i])
            candle_range = high_i - low_i if high_i != low_i else bin_size
            for b in range(bins):
                b_low = bin_edges[b]
                b_high = bin_edges[b + 1]
                overlap = max(0.0, min(high_i, b_high) - max(low_i, b_low))
                volume_at_price[b] += vol_i * (overlap / candle_range)

        poc_bin = int(np.argmax(volume_at_price))
        poc = float((bin_edges[poc_bin] + bin_edges[poc_bin + 1]) / 2)

        # Value Area = 70% of total volume around POC
        total_vol = volume_at_price.sum()
        target_vol = total_vol * 0.70
        va_vol = volume_at_price[poc_bin]
        low_idx, high_idx = poc_bin, poc_bin

        while va_vol < target_vol and (low_idx > 0 or high_idx < bins - 1):
            expand_low = volume_at_price[low_idx - 1] if low_idx > 0 else 0.0
            expand_high = volume_at_price[high_idx + 1] if high_idx < bins - 1 else 0.0
            if expand_high >= expand_low and high_idx < bins - 1:
                high_idx += 1
                va_vol += volume_at_price[high_idx]
            elif low_idx > 0:
                low_idx -= 1
                va_vol += volume_at_price[low_idx]
            else:
                break

        val = float(bin_edges[low_idx])
        vah = float(bin_edges[high_idx + 1])
        last_close = float(closes.iloc[-1])
        poc_distance_pct = round(abs(last_close - poc) / poc * 100, 3) if poc else None
        in_value_area = val <= last_close <= vah

        return {
            "poc": round(poc, 4),
            "vah": round(vah, 4),
            "val": round(val, 4),
            "poc_distance_pct": poc_distance_pct,
            "in_value_area": in_value_area,
        }
    except Exception:
        return {"poc": None, "vah": None, "val": None, "poc_distance_pct": None, "in_value_area": False}


def detect_divergence(df: pd.DataFrame, lookback: int = 5) -> Dict:
    """
    Detect RSI & MACD Divergence (Regular Bullish/Bearish).
    - Regular Bullish: price LL + RSI HL → reversal up
    - Regular Bearish: price HH + RSI LH → reversal down
    Returns: {rsi_divergence, macd_divergence, type, strength}
    """
    if df.empty or len(df) < lookback + 20:
        return {"rsi_divergence": False, "macd_divergence": False, "type": "none", "strength": 0}

    try:
        closes = df["close"].astype(float).values
        period = 14
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.zeros_like(gains)
        avg_loss = np.zeros_like(losses)
        avg_gain[period - 1] = np.mean(gains[:period])
        avg_loss[period - 1] = np.mean(losses[:period])
        for i in range(period, len(gains)):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period

        with np.errstate(divide="ignore", invalid="ignore"):
            rs = np.where(avg_loss != 0, avg_gain / avg_loss, 100.0)
        rsi_series = 100 - (100 / (1 + rs))

        n = min(lookback, len(closes) - 2, len(rsi_series) - 2)
        price_now = closes[-1]
        price_prev = closes[-n - 1]
        rsi_now = rsi_series[-1]
        rsi_prev = rsi_series[-n - 1]

        rsi_div = False
        div_type = "none"
        strength = 0

        if price_now < price_prev and rsi_now > rsi_prev and rsi_now < 50:
            rsi_div = True
            div_type = "bullish"
            strength = round(abs(rsi_now - rsi_prev), 1)
        elif price_now > price_prev and rsi_now < rsi_prev and rsi_now > 50:
            rsi_div = True
            div_type = "bearish"
            strength = round(abs(rsi_prev - rsi_now), 1)

        macd_div = False
        if len(df) >= 35:
            close_series = pd.Series(closes)
            fast_ema = close_series.ewm(span=12, adjust=False).mean()
            slow_ema = close_series.ewm(span=26, adjust=False).mean()
            macd_line = fast_ema - slow_ema
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            hist = (macd_line - signal_line).values
            hist_now = hist[-1]
            hist_prev = hist[-n - 1]
            if div_type == "bullish" and hist_now > hist_prev:
                macd_div = True
                strength = min(100, strength + 5)
            elif div_type == "bearish" and hist_now < hist_prev:
                macd_div = True
                strength = min(100, strength + 5)

        return {
            "rsi_divergence": rsi_div,
            "macd_divergence": macd_div,
            "type": div_type,
            "strength": strength,
        }
    except Exception:
        return {"rsi_divergence": False, "macd_divergence": False, "type": "none", "strength": 0}
