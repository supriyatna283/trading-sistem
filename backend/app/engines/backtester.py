"""
Automated Backtesting Engine (V4 - Phase 3 Aligned + Professional Stats)
=========================================================================
Runs the SetupGenerator over a historical window of data and simulates
trade execution with:
- Fee simulation (0.1% roundtrip)
- Fixed look-ahead bias (entry on next bar after signal)
- Phase 3 aligned threshold: min_score=16, max_score=36
- V4: Comprehensive statistics: Sharpe, Sortino, Expectancy, Calmar Ratio
- V4: signal_grade per trade (A+, A, B, C) based on score percentile
- V4: MAE tracking per trade (Maximum Adverse Excursion)
- V4: Trade breakdown by setup_type
"""

import pandas as pd
import numpy as np
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.engines.market_data import MarketDataEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.confluence import ConfluenceEngine, MAX_SCORE
from app.engines.setup_generator import SetupGenerator

logger = logging.getLogger(__name__)

# Trading fees (maker+taker for entry+exit)
FEE_RATE = 0.001  # 0.1% roundtrip (0.05% per side typical for crypto)

# HTF timeframes to fetch alongside the entry timeframe
HTF_TIMEFRAMES = ["1d", "4h"]
HTF_CANDLE_LIMIT = 300

# Phase 3 aligned threshold
MIN_SCORE = 16


def _signal_grade(score: float, max_score: float = MAX_SCORE) -> str:
    """Grade a signal based on its score as a percentage of max possible."""
    pct = (score / max_score) * 100 if max_score > 0 else 0
    if pct >= 80:
        return "A+"
    elif pct >= 65:
        return "A"
    elif pct >= 50:
        return "B"
    else:
        return "C"


class BacktestEngine:
    def __init__(self):
        self.data_engine = MarketDataEngine()
        self.structure_analyzer = MarketStructureAnalyzer()
        self.smc_engine = SmartMoneyConceptsEngine()
        self.confluence_engine = ConfluenceEngine(min_confluence_score=MIN_SCORE)
        # V4: Phase 3 aligned thresholds
        self.setup_gen = SetupGenerator(min_confluence_score=MIN_SCORE, min_rr=1.8)

    async def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        initial_capital: float = 10000.0,
        risk_per_trade_pct: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Runs a simulation over the given historical period.
        V4: Phase 3 aligned thresholds (min_score=16, max_score=36).
        Produces professional-grade statistics: Sharpe, Sortino, Expectancy, Calmar.
        """
        # 1. Fetch entry timeframe data
        df = await self.data_engine.fetch_historical_candles(
            symbol=symbol, interval=timeframe, start_ts=start_ts, end_ts=end_ts
        )

        if df.empty or len(df) < 200:
            raise ValueError("Insufficient historical data for backtesting. Need at least 200 candles.")

        logger.info(f"Starting V4 backtest for {symbol} on {timeframe} with {len(df)} candles.")

        # Pre-fetch HTF candles (1D, 4H) for the same period
        htf_dfs = await self._fetch_htf_candles(symbol, start_ts, end_ts)

        trades = []
        equity = initial_capital
        equity_curve = [{"time": int(df.iloc[0]["open_time"].timestamp() * 1000), "equity": equity}]

        active_trade = None
        pending_setup = None
        window_size = 200

        for i in range(window_size, len(df)):
            current_bar = df.iloc[i]
            current_time = int(current_bar["open_time"].timestamp() * 1000)
            current_bar_time = current_bar["open_time"]

            # --- 1. Execute Pending Entry (enter on open of NEXT bar) ---
            if pending_setup and not active_trade:
                risk_amount = equity * (risk_per_trade_pct / 100.0)
                entry_price = float(current_bar["open"])
                fee = entry_price * FEE_RATE / 2

                active_trade = {
                    "entry_time": current_time,
                    "symbol": pending_setup.symbol,
                    "direction": pending_setup.direction,
                    "entry_price": entry_price,
                    "stop_loss": pending_setup.stop_loss,
                    "take_profit_1": pending_setup.take_profit_1,
                    "risk_reward": pending_setup.risk_reward,
                    "risk_amount": risk_amount,
                    "score": pending_setup.confluence_score,
                    "max_score": MAX_SCORE,
                    "signal_grade": _signal_grade(pending_setup.confluence_score, MAX_SCORE),
                    "setup_type": pending_setup.setup_type,
                    "entry_fee": fee,
                    "mae": 0.0,
                }
                pending_setup = None

            # --- 2. Manage Active Trade ---
            if active_trade:
                high = float(current_bar["high"])
                low = float(current_bar["low"])

                trade_closed = False
                pnl = 0.0
                result = ""

                if active_trade["direction"] == "BUY":
                    adverse_distance = active_trade["entry_price"] - low
                    active_trade["mae"] = max(active_trade["mae"], adverse_distance)
                    if low <= active_trade["stop_loss"]:
                        pnl = -active_trade["risk_amount"]
                        result = "LOSS"
                        trade_closed = True
                    elif high >= active_trade["take_profit_1"]:
                        pnl = active_trade["risk_amount"] * active_trade["risk_reward"]
                        result = "WIN"
                        trade_closed = True
                else:  # SELL
                    adverse_distance = high - active_trade["entry_price"]
                    active_trade["mae"] = max(active_trade["mae"], adverse_distance)
                    if high >= active_trade["stop_loss"]:
                        pnl = -active_trade["risk_amount"]
                        result = "LOSS"
                        trade_closed = True
                    elif low <= active_trade["take_profit_1"]:
                        pnl = active_trade["risk_amount"] * active_trade["risk_reward"]
                        result = "WIN"
                        trade_closed = True

                if trade_closed:
                    exit_fee = abs(pnl) * FEE_RATE / 2
                    total_fees = active_trade.get("entry_fee", 0) + exit_fee
                    pnl_after_fees = pnl - total_fees

                    active_trade["exit_time"] = current_time
                    active_trade["pnl_gross"] = round(pnl, 2)
                    active_trade["fees"] = round(total_fees, 4)
                    active_trade["pnl"] = round(pnl_after_fees, 2)
                    active_trade["result"] = result
                    active_trade["mae"] = round(active_trade["mae"], 6)
                    equity += pnl_after_fees
                    active_trade["equity_after"] = round(equity, 2)
                    trades.append(active_trade)
                    equity_curve.append({"time": current_time, "equity": round(equity, 2)})
                    active_trade = None
                    continue

            # --- 3. Look for New Setups ---
            if not active_trade and not pending_setup:
                window_df = df.iloc[i - window_size:i].copy()

                candles_by_tf = self._build_candles_by_tf(
                    entry_tf=timeframe,
                    entry_df=window_df,
                    htf_dfs=htf_dfs,
                    as_of_time=current_bar_time,
                )

                structure = self.structure_analyzer.analyze(window_df, symbol, timeframe)
                smc = self.smc_engine.analyze(window_df, symbol, timeframe)
                confluence = self.confluence_engine.score(candles_by_tf, symbol, timeframe)

                setup = self.setup_gen.generate(
                    symbol, timeframe, confluence, smc, structure, window_df
                )

                if setup:
                    pending_setup = setup

        summary = self._calculate_summary(trades, initial_capital, equity, equity_curve)
        breakdown = self._build_breakdown(trades)

        return {
            "summary": summary,
            "trades": trades,
            "equity_curve": equity_curve,
            "breakdown": breakdown,
        }

    async def _fetch_htf_candles(
        self, symbol: str, start_ts: int, end_ts: int
    ) -> Dict[str, pd.DataFrame]:
        result = {}
        tasks = [
            self.data_engine.fetch_historical_candles(
                symbol=symbol, interval=tf,
                start_ts=start_ts, end_ts=end_ts
            )
            for tf in HTF_TIMEFRAMES
        ]
        dfs = await asyncio.gather(*tasks, return_exceptions=True)
        for tf, df in zip(HTF_TIMEFRAMES, dfs):
            if isinstance(df, Exception):
                logger.warning(f"HTF fetch failed for {tf}: {df}")
                result[tf] = pd.DataFrame()
            else:
                result[tf] = df
        return result

    def _build_candles_by_tf(
        self,
        entry_tf: str,
        entry_df: pd.DataFrame,
        htf_dfs: Dict[str, pd.DataFrame],
        as_of_time,
        htf_window: int = 200,
    ) -> Dict[str, pd.DataFrame]:
        candles_by_tf = {entry_tf: entry_df}
        for tf, htf_df in htf_dfs.items():
            if htf_df.empty:
                continue
            available = htf_df[htf_df["open_time"] <= as_of_time]
            if available.empty:
                continue
            candles_by_tf[tf] = available.tail(htf_window).reset_index(drop=True)
        return candles_by_tf

    def _calculate_summary(
        self, trades: list, initial_capital: float,
        final_equity: float, equity_curve: list
    ) -> Dict[str, Any]:
        """Calculate comprehensive professional-grade backtest statistics."""
        wins = [t for t in trades if t["result"] == "WIN"]
        losses = [t for t in trades if t["result"] == "LOSS"]
        total_trades = len(trades)
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        net_profit = gross_profit - gross_loss
        total_fees = sum(t.get("fees", 0) for t in trades)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        pnls = [t["pnl"] for t in trades]
        largest_win = max(pnls) if pnls else 0
        largest_loss = min(pnls) if pnls else 0
        avg_win = gross_profit / win_count if win_count > 0 else 0
        avg_loss = gross_loss / loss_count if loss_count > 0 else 0
        avg_rr = round(sum(t.get("risk_reward", 0) for t in trades) / total_trades, 2) if total_trades > 0 else 0

        # Consecutive losses
        max_consecutive_losses = 0
        current_streak = 0
        for t in trades:
            if t["result"] == "LOSS":
                current_streak += 1
                max_consecutive_losses = max(max_consecutive_losses, current_streak)
            else:
                current_streak = 0

        # Max Drawdown
        peak = initial_capital
        max_dd = 0.0
        for eq_point in equity_curve:
            if eq_point["equity"] > peak:
                peak = eq_point["equity"]
            dd = (peak - eq_point["equity"]) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # Expectancy
        loss_rate = (loss_count / total_trades) if total_trades > 0 else 0
        expectancy = ((win_rate / 100) * avg_win) - (loss_rate * avg_loss)
        expectancy_pct = (expectancy / initial_capital) * 100 if initial_capital > 0 else 0

        # Calmar Ratio
        total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100
        if len(equity_curve) >= 2:
            period_ms = equity_curve[-1]["time"] - equity_curve[0]["time"]
            period_years = period_ms / (1000 * 60 * 60 * 24 * 365)
            annualized_return = (total_return_pct / period_years) if period_years > 0.01 else total_return_pct
            calmar_ratio = round(annualized_return / max_dd, 3) if max_dd > 0 else 0.0
        else:
            calmar_ratio = 0.0

        # Sharpe & Sortino Ratios
        sharpe_ratio = 0.0
        sortino_ratio = 0.0
        if len(equity_curve) >= 10:
            equities = np.array([e["equity"] for e in equity_curve])
            returns = np.diff(equities) / equities[:-1]
            if len(returns) > 1:
                mean_ret = np.mean(returns)
                std_ret = np.std(returns)
                if std_ret > 0:
                    sharpe_ratio = float(mean_ret / std_ret * np.sqrt(len(returns)))
                downside = returns[returns < 0]
                sortino_std = np.std(downside) if len(downside) > 1 else std_ret
                if sortino_std > 0:
                    sortino_ratio = float(mean_ret / sortino_std * np.sqrt(len(returns)))

        # Grade breakdown
        grade_counts: Dict[str, int] = {"A+": 0, "A": 0, "B": 0, "C": 0}
        for t in trades:
            g = t.get("signal_grade", "C")
            grade_counts[g] = grade_counts.get(g, 0) + 1

        return {
            "initial_capital": initial_capital,
            "final_equity": round(final_equity, 2),
            "total_return_pct": round(total_return_pct, 2),
            "net_profit": round(net_profit, 2),
            "total_fees": round(total_fees, 2),
            "total_trades": total_trades,
            "wins": win_count,
            "losses": loss_count,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "avg_rr": avg_rr,
            "largest_win": round(largest_win, 2),
            "largest_loss": round(largest_loss, 2),
            "max_consecutive_losses": max_consecutive_losses,
            # V4: Professional Ratios
            "sharpe_ratio": round(sharpe_ratio, 3),
            "sortino_ratio": round(sortino_ratio, 3),
            "calmar_ratio": calmar_ratio,
            "expectancy": round(expectancy, 2),
            "expectancy_pct": round(expectancy_pct, 4),
            "grade_counts": grade_counts,
        }

    def _build_breakdown(self, trades: list) -> list:
        """Build per-setup-type breakdown stats."""
        breakdown: Dict[str, Dict] = {}
        for t in trades:
            st = t.get("setup_type", "Unknown")
            if st not in breakdown:
                breakdown[st] = {"total": 0, "wins": 0, "losses": 0, "pnl": 0.0}
            breakdown[st]["total"] += 1
            breakdown[st]["pnl"] = round(breakdown[st]["pnl"] + t.get("pnl", 0), 2)
            if t["result"] == "WIN":
                breakdown[st]["wins"] += 1
            else:
                breakdown[st]["losses"] += 1

        result = []
        for setup_type, stats in breakdown.items():
            wr = round((stats["wins"] / stats["total"] * 100) if stats["total"] > 0 else 0, 1)
            result.append({
                "setup_type": setup_type,
                "total": stats["total"],
                "wins": stats["wins"],
                "losses": stats["losses"],
                "win_rate": wr,
                "pnl": stats["pnl"],
            })
        result.sort(key=lambda x: x["total"], reverse=True)
        return result
