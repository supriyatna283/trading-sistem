import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class SMTResult:
    is_divergent: bool
    smt_type: str        # BULLISH | BEARISH | NONE
    primary_symbol: str
    correlated_symbol: str
    description: str

class SMTDivergenceEngine:
    """
    Smart Money Tool (SMT) Divergence Engine.
    Compares two correlated assets (e.g. BTC vs ETH) to find structural divergences.
    Bullish SMT: Primary makes Lower Low, Secondary makes Higher Low.
    Bearish SMT: Primary makes Higher High, Secondary makes Lower High.
    """

    def _find_recent_swings(self, df: pd.DataFrame, window: int = 5):
        """Finds the most recent significant high and low."""
        if len(df) < window * 2: return None, None
        
        # Simplified swing detection for last N periods vs previous N periods
        recent = df.tail(window)
        prev = df.iloc[-window*2:-window]

        recent_high = recent['high'].max()
        recent_low = recent['low'].min()
        
        prev_high = prev['high'].max()
        prev_low = prev['low'].min()
        
        return {
            "hh": recent_high > prev_high,
            "hl": recent_low > prev_low,
            "lh": recent_high < prev_high,
            "ll": recent_low < prev_low,
        }

    def analyze(self, primary_df: pd.DataFrame, secondary_df: pd.DataFrame, 
                primary_sym: str, secondary_sym: str) -> SMTResult:
        
        prim_swings = self._find_recent_swings(primary_df)
        sec_swings = self._find_recent_swings(secondary_df)

        if not prim_swings or not sec_swings:
            return SMTResult(False, "NONE", primary_sym, secondary_sym, "Insufficient data for SMT analysis.")

        # Bullish SMT: Primary makes LL, Secondary makes HL
        if prim_swings["ll"] and sec_swings["hl"]:
            return SMTResult(
                True, "BULLISH", primary_sym, secondary_sym,
                f"Bullish SMT: {primary_sym} made a Lower Low, but {secondary_sym} made a Higher Low. Smart Money accumulation detected."
            )
        
        # Bearish SMT: Primary makes HH, Secondary makes LH
        if prim_swings["hh"] and sec_swings["lh"]:
            return SMTResult(
                True, "BEARISH", primary_sym, secondary_sym,
                f"Bearish SMT: {primary_sym} made a Higher High, but {secondary_sym} made a Lower High. Smart Money distribution detected."
            )

        return SMTResult(False, "NONE", primary_sym, secondary_sym, "No structural divergence detected.")
