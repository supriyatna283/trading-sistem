import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict, Any


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
    Calculate VWAP (Volume Weighted Average Price) with Daily Anchor.
    VWAP = Σ(Typical Price × Volume) / Σ(Volume) reset every day.
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

        if "open_time" in df.columns:
            # Daily Anchored VWAP
            # Make sure it's datetime
            if not pd.api.types.is_datetime64_any_dtype(df["open_time"]):
                df["open_time"] = pd.to_datetime(df["open_time"])
            df["date"] = df["open_time"].dt.date
            df["cum_tp_vol"] = df.groupby("date")["tp_vol"].cumsum()
            df["cum_vol"] = df.groupby("date")["vol"].cumsum()
        else:
            # Fallback if no time column (just use all available data as session)
            df["cum_tp_vol"] = df["tp_vol"].cumsum()
            df["cum_vol"] = df["vol"].cumsum()

        last_row = df.iloc[-1]
        cum_vol = float(last_row["cum_vol"])
        cum_tp_vol = float(last_row["cum_tp_vol"])

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


def detect_divergence(df: pd.DataFrame, swing_lookback: int = 3, max_bars: int = 50) -> Dict:
    """
    Detect RSI & MACD Divergence using genuine swing pivot comparison.

    V3 FIX: Correct RSI series alignment.
    `rsi_aligned` now has length == len(closes), with index 0 = nan and
    index i = RSI value for bar i. This ensures `rsi_aligned[swing_idx]`
    returns the RSI corresponding to the correct price bar.

    Method:
    - Regular Bullish: price makes LOWER LOW at pivot, RSI makes HIGHER LOW
    - Regular Bearish: price makes HIGHER HIGH at pivot, RSI makes LOWER HIGH

    Returns: {rsi_divergence, macd_divergence, type, strength}
    """
    if df.empty or len(df) < swing_lookback * 2 + 20:
        return {"rsi_divergence": False, "macd_divergence": False, "type": "none", "strength": 0}

    try:
        closes = df["close"].astype(float).values
        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        n = len(closes)

        # Build RSI series — length == n (aligned with closes)
        # Use pandas EWM for proper Wilder's smoothing (same as calculate_rsi)
        period = 14
        close_series = pd.Series(closes)
        deltas = close_series.diff()
        gains = deltas.clip(lower=0)
        losses = (-deltas).clip(lower=0)
        avg_gain = gains.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = losses.ewm(com=period - 1, min_periods=period).mean()
        with np.errstate(divide="ignore", invalid="ignore"):
            rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi_series = (100 - (100 / (1 + rs))).values  # length == n, index-aligned with closes

        # Find swing lows (for bullish divergence) using 3-bar pivot
        lb = swing_lookback
        search_start = max(lb, n - max_bars)
        swing_lows = []   # (bar_index, low_price, rsi_value)
        swing_highs = []  # (bar_index, high_price, rsi_value)

        for i in range(search_start, n - lb):
            rsi_val = rsi_series[i]
            if np.isnan(rsi_val):
                continue

            # Swing Low: current low is lower than lb bars on each side
            if all(lows[i] <= lows[i - j] for j in range(1, lb + 1)) and \
               all(lows[i] <= lows[i + j] for j in range(1, lb + 1)):
                swing_lows.append((i, float(lows[i]), float(rsi_val)))

            # Swing High: current high is higher than lb bars on each side
            if all(highs[i] >= highs[i - j] for j in range(1, lb + 1)) and \
               all(highs[i] >= highs[i + j] for j in range(1, lb + 1)):
                swing_highs.append((i, float(highs[i]), float(rsi_val)))

        rsi_div = False
        div_type = "none"
        strength = 0

        # --- Regular Bullish Divergence ---
        # Price: Lower Low (LL) | RSI: Higher Low (HL) → reversal up
        if len(swing_lows) >= 2:
            prev_low = swing_lows[-2]
            curr_low = swing_lows[-1]
            price_ll = curr_low[1] < prev_low[1]    # Price made lower low
            rsi_hl = curr_low[2] > prev_low[2]      # RSI made higher low
            if price_ll and rsi_hl and curr_low[2] < 50:  # RSI in bearish territory
                rsi_div = True
                div_type = "bullish"
                price_diff = abs(curr_low[1] - prev_low[1]) / prev_low[1] * 100
                rsi_diff = abs(curr_low[2] - prev_low[2])
                strength = round(min(100, rsi_diff * 2 + price_diff), 1)

        # --- Regular Bearish Divergence ---
        # Price: Higher High (HH) | RSI: Lower High (LH) → reversal down
        if not rsi_div and len(swing_highs) >= 2:
            prev_high = swing_highs[-2]
            curr_high = swing_highs[-1]
            price_hh = curr_high[1] > prev_high[1]  # Price made higher high
            rsi_lh = curr_high[2] < prev_high[2]    # RSI made lower high
            if price_hh and rsi_lh and curr_high[2] > 50:  # RSI in bullish territory
                rsi_div = True
                div_type = "bearish"
                price_diff = abs(curr_high[1] - prev_high[1]) / prev_high[1] * 100
                rsi_diff = abs(curr_high[2] - prev_high[2])
                strength = round(min(100, rsi_diff * 2 + price_diff), 1)

        # --- MACD Divergence Confirmation ---
        macd_div = False
        if rsi_div and len(df) >= 35:
            close_s = pd.Series(closes)
            fast_ema = close_s.ewm(span=12, adjust=False).mean()
            slow_ema = close_s.ewm(span=26, adjust=False).mean()
            macd_line = fast_ema - slow_ema
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            hist = (macd_line - signal_line).values

            if div_type == "bullish" and len(swing_lows) >= 2:
                # MACD hist should also be making higher lows at the same pivots
                h_prev = hist[swing_lows[-2][0]] if swing_lows[-2][0] < len(hist) else None
                h_curr = hist[swing_lows[-1][0]] if swing_lows[-1][0] < len(hist) else None
                if h_prev is not None and h_curr is not None and not np.isnan(h_prev) and not np.isnan(h_curr) and h_curr > h_prev:
                    macd_div = True
                    strength = min(100, strength + 10)

            elif div_type == "bearish" and len(swing_highs) >= 2:
                h_prev = hist[swing_highs[-2][0]] if swing_highs[-2][0] < len(hist) else None
                h_curr = hist[swing_highs[-1][0]] if swing_highs[-1][0] < len(hist) else None
                if h_prev is not None and h_curr is not None and not np.isnan(h_prev) and not np.isnan(h_curr) and h_curr < h_prev:
                    macd_div = True
                    strength = min(100, strength + 10)

        return {
            "rsi_divergence": rsi_div,
            "macd_divergence": macd_div,
            "type": div_type,
            "strength": strength,
        }
    except Exception:
        return {"rsi_divergence": False, "macd_divergence": False, "type": "none", "strength": 0}


# ══════════════════════════════════════════════════════════════════
# TIER 2 — POWER FEATURES (Phase 3)
# ══════════════════════════════════════════════════════════════════

def calculate_adx(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """
    Calculate Average Directional Index (ADX).
    ADX > 25 = Strong Trend
    ADX < 20 = Sideways / Ranging
    Returns the latest ADX value.
    """
    if df.empty or len(df) < period * 2:
        return None

    try:
        high = df["high"].astype(float).values
        low = df["low"].astype(float).values
        close = df["close"].astype(float).values

        tr1 = np.abs(high[1:] - low[1:])
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.maximum(np.maximum(tr1, tr2), tr3)

        up_move = high[1:] - high[:-1]
        down_move = low[:-1] - low[1:]

        pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        def smma(series, length):
            res = np.zeros_like(series)
            if len(series) < length:
                return res
            res[length - 1] = np.mean(series[:length])
            for i in range(length, len(series)):
                res[i] = (res[i - 1] * (length - 1) + series[i]) / length
            return res

        tr_smma = smma(tr, period)
        pos_dm_smma = smma(pos_dm, period)
        neg_dm_smma = smma(neg_dm, period)

        with np.errstate(divide="ignore", invalid="ignore"):
            pos_di = np.where(tr_smma > 0, 100 * pos_dm_smma / tr_smma, 0.0)
            neg_di = np.where(tr_smma > 0, 100 * neg_dm_smma / tr_smma, 0.0)
            dx = np.where((pos_di + neg_di) > 0, 100 * np.abs(pos_di - neg_di) / (pos_di + neg_di), 0.0)

        adx = smma(dx, period)

        last_adx = float(adx[-1])
        return round(last_adx, 2) if not np.isnan(last_adx) else None
    except Exception:
        return None


def detect_candle_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detect reversal candle patterns on the latest closed candles.
    Checks for: Engulfing, Pin Bar (Hammer/Shooting Star), Doji.
    Returns: {"pattern": str|None, "bullish": bool}
    """
    if df.empty or len(df) < 2:
        return {"pattern": None, "bullish": False}

    try:
        # We look at the last two candles
        curr = df.iloc[-1]
        prev = df.iloc[-2]

        c_open, c_high, c_low, c_close = float(curr["open"]), float(curr["high"]), float(curr["low"]), float(curr["close"])
        p_open, p_high, p_low, p_close = float(prev["open"]), float(prev["high"]), float(prev["low"]), float(prev["close"])

        c_body = abs(c_close - c_open)
        c_range = c_high - c_low
        p_body = abs(p_close - p_open)

        if c_range == 0:
            return {"pattern": None, "bullish": False}

        c_is_bullish = c_close > c_open
        p_is_bullish = p_close > p_open

        c_upper_wick = c_high - max(c_open, c_close)
        c_lower_wick = min(c_open, c_close) - c_low

        # 1. Engulfing
        # Bullish Engulfing: prev is red, curr is green, curr body engulfs prev body
        if not p_is_bullish and c_is_bullish and c_close >= p_open and c_open <= p_close and c_body > p_body:
            return {"pattern": "engulfing", "bullish": True}
        
        # Bearish Engulfing: prev is green, curr is red, curr body engulfs prev body
        if p_is_bullish and not c_is_bullish and c_close <= p_open and c_open >= p_close and c_body > p_body:
            return {"pattern": "engulfing", "bullish": False}

        # 2. Pin Bar
        # Bullish Pin Bar (Hammer): long lower wick (> 2x body), small upper wick, close in top 30% of range
        if c_lower_wick > (2 * c_body) and c_upper_wick < c_body and (c_close - c_low) / c_range > 0.7:
            return {"pattern": "pin_bar", "bullish": True}
        
        # Bearish Pin Bar (Shooting Star): long upper wick (> 2x body), small lower wick, close in bottom 30% of range
        if c_upper_wick > (2 * c_body) and c_lower_wick < c_body and (c_high - c_close) / c_range > 0.7:
            return {"pattern": "pin_bar", "bullish": False}

        # 3. Doji
        # Real body is less than 5% of total candle range
        if c_body <= (c_range * 0.05) and c_range > (c_close * 0.001): # Ensure range is not just a flatline
            # Doji doesn't inherently have a direction, but it indicates exhaustion.
            # We can classify it as neutral/none for strong directional booster, but let's return it
            return {"pattern": "doji", "bullish": False} # bullish flag means nothing here

        return {"pattern": None, "bullish": False}
    except Exception:
        return {"pattern": None, "bullish": False}
