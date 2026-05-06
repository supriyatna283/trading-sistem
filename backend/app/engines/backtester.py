"""
Automated Backtesting Engine (V2 - Realistic)
================================================
Runs the SetupGenerator over a historical window of data and simulates
trade execution with:
- Fee simulation (0.1% roundtrip)
- Fixed look-ahead bias (entry on next bar after signal)
- Extended summary statistics (avg R:R, largest win/loss, etc.)
"""

import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict, Any

from app.engines.market_data import MarketDataEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.confluence import ConfluenceEngine
from app.engines.setup_generator import SetupGenerator

logger = logging.getLogger(__name__)

# V2: Trading fees (maker+taker for entry+exit)
FEE_RATE = 0.001  # 0.1% roundtrip (0.05% per side typical for crypto)


class BacktestEngine:
    def __init__(self):
        self.data_engine = MarketDataEngine()
        self.structure_analyzer = MarketStructureAnalyzer()
        self.smc_engine = SmartMoneyConceptsEngine()
        self.confluence_engine = ConfluenceEngine()
        self.setup_gen = SetupGenerator(min_confluence_score=5, min_rr=1.5)

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
        V2: Includes fee simulation and fixes look-ahead bias.
        """
        # 1. Fetch historical data
        df = await self.data_engine.fetch_historical_candles(
            symbol=symbol, interval=timeframe, start_ts=start_ts, end_ts=end_ts
        )

        if df.empty or len(df) < 200:
            raise ValueError("Insufficient historical data for backtesting. Need at least 200 candles.")

        logger.info(f"Starting backtest for {symbol} on {timeframe} with {len(df)} candles.")

        trades = []
        equity = initial_capital
        equity_curve = [{"time": int(df.iloc[0]["open_time"].timestamp() * 1000), "equity": equity}]

        # Simulation variables
        active_trade = None
        pending_setup = None  # V2: holds setup to enter on NEXT bar
        window_size = 200

        for i in range(window_size, len(df)):
            current_bar = df.iloc[i]
            current_time = int(current_bar["open_time"].timestamp() * 1000)

            # --- 1. Execute Pending Entry (V2: enter on THIS bar if setup was generated LAST bar) ---
            if pending_setup and not active_trade:
                risk_amount = equity * (risk_per_trade_pct / 100.0)
                entry_price = float(current_bar["open"])  # Enter on open of NEXT bar

                # V2: Apply entry fee
                fee = entry_price * FEE_RATE / 2  # Half the roundtrip fee

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
                    "setup_type": pending_setup.setup_type,
                    "entry_fee": fee,
                }
                pending_setup = None

            # --- 2. Manage Active Trade ---
            if active_trade:
                high = float(current_bar["high"])
                low = float(current_bar["low"])

                trade_closed = False
                pnl = 0.0
                result = ""
                exit_fee = 0.0

                if active_trade["direction"] == "BUY":
                    # Check SL hit first (worst case first)
                    if low <= active_trade["stop_loss"]:
                        pnl = -active_trade["risk_amount"]
                        result = "LOSS"
                        trade_closed = True
                    # Check TP1 hit
                    elif high >= active_trade["take_profit_1"]:
                        pnl = active_trade["risk_amount"] * active_trade["risk_reward"]
                        result = "WIN"
                        trade_closed = True
                else:  # SELL
                    # Check SL hit first
                    if high >= active_trade["stop_loss"]:
                        pnl = -active_trade["risk_amount"]
                        result = "LOSS"
                        trade_closed = True
                    # Check TP1 hit
                    elif low <= active_trade["take_profit_1"]:
                        pnl = active_trade["risk_amount"] * active_trade["risk_reward"]
                        result = "WIN"
                        trade_closed = True

                if trade_closed:
                    # V2: Apply exit fee
                    exit_fee = abs(pnl) * FEE_RATE / 2
                    total_fees = active_trade.get("entry_fee", 0) + exit_fee
                    pnl_after_fees = pnl - total_fees

                    active_trade["exit_time"] = current_time
                    active_trade["pnl_gross"] = round(pnl, 2)
                    active_trade["fees"] = round(total_fees, 4)
                    active_trade["pnl"] = round(pnl_after_fees, 2)
                    active_trade["result"] = result
                    equity += pnl_after_fees
                    active_trade["equity_after"] = round(equity, 2)
                    trades.append(active_trade)
                    equity_curve.append({"time": current_time, "equity": round(equity, 2)})
                    active_trade = None
                    continue  # Don't look for new setup on same bar we exited

            # --- 3. Look for New Setups (V2: setup generated here → entry on NEXT bar) ---
            if not active_trade and not pending_setup:
                window_df = df.iloc[i - window_size:i].copy()

                # Mock multi-TF dict (single TF backtest limitation)
                mock_tfs = {timeframe: window_df}

                # Run the analysis pipeline
                structure = self.structure_analyzer.analyze(window_df, symbol, timeframe)
                smc = self.smc_engine.analyze(window_df, symbol, timeframe)
                confluence = self.confluence_engine.score(mock_tfs, symbol, timeframe)

                setup = self.setup_gen.generate(
                    symbol, timeframe, confluence, smc, structure, window_df
                )

                if setup:
                    pending_setup = setup  # V2: defer entry to next bar

        # Calculate summary statistics
        summary = self._calculate_summary(trades, initial_capital, equity, equity_curve)

        return {
            "summary": summary,
            "trades": trades,
            "equity_curve": equity_curve,
        }

    def _calculate_summary(
        self, trades: list, initial_capital: float,
        final_equity: float, equity_curve: list
    ) -> Dict[str, Any]:
        """Calculate comprehensive backtest summary statistics."""
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

        # V2: Extended stats
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

        # Max Drawdown calculation
        peak = initial_capital
        max_dd = 0.0
        for eq_point in equity_curve:
            if eq_point["equity"] > peak:
                peak = eq_point["equity"]
            dd = (peak - eq_point["equity"]) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return {
            "initial_capital": initial_capital,
            "final_equity": round(final_equity, 2),
            "total_return_pct": round(((final_equity - initial_capital) / initial_capital) * 100, 2),
            "net_profit": round(net_profit, 2),
            "total_fees": round(total_fees, 2),
            "total_trades": total_trades,
            "wins": win_count,
            "losses": loss_count,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_dd, 2),
            # V2: Extended stats
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "avg_rr": avg_rr,
            "largest_win": round(largest_win, 2),
            "largest_loss": round(largest_loss, 2),
            "max_consecutive_losses": max_consecutive_losses,
        }
