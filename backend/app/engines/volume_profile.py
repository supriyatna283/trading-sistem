import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class VolumeProfileResult:
    poc_price: float
    vah_price: float
    val_price: float
    value_area_pct: float
    high_volume_nodes: List[float]
    low_volume_nodes: List[float]

class VolumeProfileEngine:
    """
    Fixed Range Volume Profile (FRVP) Calculator.
    Splits price range into bins and sums volume for each bin.
    Identifies Point of Control (POC), Value Area High (VAH), and Value Area Low (VAL).
    """

    def analyze(self, df: pd.DataFrame, bins: int = 50, value_area_pct: float = 0.70) -> Optional[VolumeProfileResult]:
        if df is None or len(df) < 20 or "volume" not in df.columns:
            return None

        # Price range
        min_p = df['low'].min()
        max_p = df['high'].max()
        if min_p == max_p:
            return None

        # Create bins
        bin_edges = np.linspace(min_p, max_p, bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        volume_profile = np.zeros(bins)

        # Distribute volume across bins
        for _, row in df.iterrows():
            low = row['low']
            high = row['high']
            vol = row['volume']

            # Find overlapping bins
            # Simplified distribution: give all volume to the bin closest to typical price
            # or distribute evenly. We distribute evenly across bins that fall between low and high
            overlap_mask = (bin_edges[:-1] <= high) & (bin_edges[1:] >= low)
            overlapping_bins_count = np.sum(overlap_mask)
            
            if overlapping_bins_count > 0:
                volume_profile[overlap_mask] += vol / overlapping_bins_count
            else:
                # If high == low, just add to nearest bin
                idx = (np.abs(bin_centers - (high+low)/2)).argmin()
                volume_profile[idx] += vol

        # Calculate POC
        poc_idx = np.argmax(volume_profile)
        poc_price = float(bin_centers[poc_idx])

        # Calculate Value Area (70% of total volume)
        total_vol = np.sum(volume_profile)
        target_vol = total_vol * value_area_pct
        
        va_vol = volume_profile[poc_idx]
        lower_idx = poc_idx
        upper_idx = poc_idx

        while va_vol < target_vol and (lower_idx > 0 or upper_idx < bins - 1):
            lower_vol = volume_profile[lower_idx - 1] if lower_idx > 0 else 0
            upper_vol = volume_profile[upper_idx + 1] if upper_idx < bins - 1 else 0
            
            if lower_vol >= upper_vol and lower_idx > 0:
                lower_idx -= 1
                va_vol += volume_profile[lower_idx]
            elif upper_idx < bins - 1:
                upper_idx += 1
                va_vol += volume_profile[upper_idx]
            else:
                break

        val_price = float(bin_centers[lower_idx])
        vah_price = float(bin_centers[upper_idx])

        # Find High Volume Nodes (HVN) and Low Volume Nodes (LVN)
        # Simplified: peaks and troughs in the profile
        hvns = []
        lvns = []
        for i in range(1, bins-1):
            if volume_profile[i] > volume_profile[i-1] and volume_profile[i] > volume_profile[i+1]:
                hvns.append(float(bin_centers[i]))
            if volume_profile[i] < volume_profile[i-1] and volume_profile[i] < volume_profile[i+1]:
                lvns.append(float(bin_centers[i]))

        return VolumeProfileResult(
            poc_price=poc_price,
            vah_price=vah_price,
            val_price=val_price,
            value_area_pct=value_area_pct,
            high_volume_nodes=hvns,
            low_volume_nodes=lvns
        )
