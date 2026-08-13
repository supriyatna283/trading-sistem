"""
Trading Intelligence Backtester (V6)
======================================
Replays ConfluenceEngine across historical candles to measure signal accuracy.

Strategy:
- Walk forward through candle data (no look-ahead bias)
- At each candle, run the full ConfluenceEngine with all preceding candles as context
- If a signal fires, simulate entry/exit based on subsequent price action
- Track: Win Rate, Expectancy, Max Drawdown, Sharpe Ratio, Profit Factor
"""

import logging
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Minimum candles needed before generating first signal (warm-up period)
WARMUP_CANDLES = 200

# ATR multiplier for determining "max bars to hold" a position
MAX_HOLD_BARS = 48   # Default max hold (48 × TF bars)


class BacktestResult:
    """Structured backtest result."""

    def __init__(self):
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = []
        self.initial_capital: float = 10000.0
        self.final_capital: float = 10000.0

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def winning_trades(self) -> int:
        return sum(1 for t in self.trades if t.get("pnl", 0) > 0)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def avg_win(self) -> float:
        wins = [t["pnl"] for t in self.trades if t.get("pnl", 0) > 0]
        return float(np.mean(wins)) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        losses = [t["pnl"] for t in self.trades if t.get("pnl", 0) < 0]
        return float(np.mean(losses)) if losses else 0.0

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t["pnl"] for t in self.trades if t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t["pnl"] for t in self.trades if t.get("pnl", 0) < 0))
        return round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf")

    @property
    def max_drawdown_pct(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for val in self.equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100
            if dd > max_dd:
                max_dd = dd
        return round(max_dd, 2)

    @property
    def sharpe_ratio(self) -> float:
        if len(self.trades) < 3:
            return 0.0
        returns = [t.get("return_pct", 0) for t in self.trades]
        mean_ret = float(np.mean(returns))
        std_ret = float(np.std(returns))
        if std_ret == 0:
            return 0.0
        return round(mean_ret / std_ret * np.sqrt(252), 2)

    @property
    def expectancy(self) -> float:
        if not self.trades:
            return 0.0
        wr = self.win_rate / 100
        return round(wr * self.avg_win + (1 - wr) * self.avg_loss, 2)

    def to_dict(self) -> Dict:
        return {
            "summary": {
                "total_trades": self.total_trades,
                "win_rate": round(self.win_rate, 1),
                "profit_factor": self.profit_factor,
                "expectancy": self.expectancy,
                "avg_win": round(self.avg_win, 2),
                "avg_loss": round(self.avg_loss, 2),
                "max_drawdown_pct": self.max_drawdown_pct,
                "sharpe_ratio": self.sharpe_ratio,
                "initial_capital": self.initial_capital,
                "final_capital": round(self.final_capital, 2),
                "total_return_pct": round(
                    (self.final_capital - self.initial_capital) / self.initial_capital * 100, 2
                ),
            },
            "equity_curve": self.equity_curve,
            "trades": self.trades,
        }


class BacktestEngine:
    """
    Walk-forward backtester using the full ConfluenceEngine.

    The key design principle is NO look-ahead bias:
    - At bar N, we only use bars [0..N] as input
    - Signals are evaluated starting from bar WARMUP_CANDLES
    - Entry is simulated at the OPEN of the next bar after signal fires
    """

    def __init__(self):
        pass

    async def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        initial_capital: float = 10000.0,
        risk_per_trade_pct: float = 1.0,
    ) -> Dict:
        """
        Run a full walk-forward backtest.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT")
            timeframe: Candle timeframe (e.g. "1h", "4h")
            start_ts: Start timestamp in milliseconds (UTC)
            end_ts: End timestamp in milliseconds (UTC)
            initial_capital: Starting capital in USDT
            risk_per_trade_pct: Risk per trade as % of capital
        """
        import pandas as pd
        from app.engines.market_data import MarketDataEngine
        from app.engines.confluence import ConfluenceEngine
        from app.engines.market_structure import MarketStructureAnalyzer
        from app.engines.smart_money import SmartMoneyConceptsEngine
        from app.engines.setup_generator import SetupGenerator, _estimate_atr

        logger.info(f"🔬 Backtest: {symbol}/{timeframe} from {start_ts} to {end_ts}")

        data_engine = MarketDataEngine()
        confluence_engine = ConfluenceEngine()
        smc_engine = SmartMoneyConceptsEngine()
        structure_analyzer = MarketStructureAnalyzer()
        setup_gen = SetupGenerator(min_confluence_score=18, min_rr=1.8)

        # Fetch the full candle history — use a large limit (1000 candles max)
        limit = min(1000, int((end_ts - start_ts) / 1000 / _tf_to_seconds(timeframe)) + WARMUP_CANDLES + 10)
        full_df = await data_engine.get_candles(symbol, timeframe, limit)

        if full_df is None or full_df.empty:
            raise ValueError(f"No candle data available for {symbol}/{timeframe}")

        # Filter to the requested date range
        if "open_time" in full_df.columns:
            full_df["open_time_ts"] = pd.to_datetime(full_df["open_time"]).astype(int) // 10**6
            full_df = full_df[
                (full_df["open_time_ts"] >= start_ts) & (full_df["open_time_ts"] <= end_ts)
            ].reset_index(drop=True)

        if len(full_df) < WARMUP_CANDLES + 10:
            raise ValueError(
                f"Insufficient data: {len(full_df)} candles. Need at least {WARMUP_CANDLES + 10}."
            )

        result = BacktestResult()
        result.initial_capital = initial_capital
        capital = initial_capital
        result.equity_curve.append(capital)

        in_trade = False
        trade_direction: Optional[str] = None
        entry_price: float = 0.0
        stop_loss: float = 0.0
        take_profit: float = 0.0
        position_size: float = 0.0
        trade_entry_bar: int = 0
        signal_count = 0

        # Walk-forward loop
        for i in range(WARMUP_CANDLES, len(full_df) - 1):
            current_bar = full_df.iloc[i]
            next_bar = full_df.iloc[i + 1]

            # ── Manage open trade ─────────────────────────────────────────
            if in_trade:
                high_next = float(next_bar["high"])
                low_next = float(next_bar["low"])
                close_next = float(next_bar["close"])

                # Check SL hit
                sl_hit = (
                    (trade_direction == "BUY" and low_next <= stop_loss) or
                    (trade_direction == "SELL" and high_next >= stop_loss)
                )
                # Check TP hit
                tp_hit = (
                    (trade_direction == "BUY" and high_next >= take_profit) or
                    (trade_direction == "SELL" and low_next <= take_profit)
                )
                # Max hold period
                bars_held = i - trade_entry_bar
                max_hold_hit = bars_held >= MAX_HOLD_BARS

                if sl_hit or tp_hit or max_hold_hit:
                    if sl_hit:
                        exit_price = stop_loss
                    elif tp_hit:
                        exit_price = take_profit
                    else:
                        exit_price = close_next  # Close at market on max hold

                    if trade_direction == "BUY":
                        pnl = (exit_price - entry_price) * position_size
                        return_pct = (exit_price - entry_price) / entry_price * 100
                    else:
                        pnl = (entry_price - exit_price) * position_size
                        return_pct = (entry_price - exit_price) / entry_price * 100

                    capital += pnl
                    result.equity_curve.append(capital)
                    result.trades.append({
                        "bar_index": i,
                        "direction": trade_direction,
                        "entry_price": round(entry_price, 6),
                        "exit_price": round(exit_price, 6),
                        "stop_loss": round(stop_loss, 6),
                        "take_profit": round(take_profit, 6),
                        "pnl": round(pnl, 2),
                        "return_pct": round(return_pct, 2),
                        "exit_reason": "SL" if sl_hit else ("TP" if tp_hit else "MAX_HOLD"),
                        "bars_held": bars_held,
                    })
                    in_trade = False
                continue  # Don't open new trade on same bar

            # ── Generate signal at bar i ──────────────────────────────────
            window_df = full_df.iloc[:i + 1].copy()
            # Need 4H context: use the same 1H data as proxy (simplification)
            candles_by_tf = {timeframe: window_df}

            try:
                confluence = confluence_engine.score(candles_by_tf, symbol, timeframe)
                smc = smc_engine.analyze(window_df, symbol, timeframe)
                structure = structure_analyzer.analyze(window_df, symbol, timeframe)

                setup = setup_gen.generate(symbol, timeframe, confluence, smc, structure, window_df)
            except Exception:
                continue

            if setup is None:
                continue

            signal_count += 1
            # Entry: open price of next bar (avoids look-ahead)
            sim_entry = float(next_bar["open"])
            atr = _estimate_atr(window_df.tail(20))

            if setup.direction == "BUY":
                sim_sl = sim_entry - atr * 1.5
                sim_tp = sim_entry + atr * 3.0  # 2R
            else:
                sim_sl = sim_entry + atr * 1.5
                sim_tp = sim_entry - atr * 3.0

            risk_amount = capital * (risk_per_trade_pct / 100)
            risk_per_unit = abs(sim_entry - sim_sl)
            if risk_per_unit <= 0:
                continue

            position_size = risk_amount / risk_per_unit

            in_trade = True
            trade_direction = setup.direction
            entry_price = sim_entry
            stop_loss = sim_sl
            take_profit = sim_tp
            trade_entry_bar = i

        result.final_capital = capital
        logger.info(
            f"✅ Backtest done: {result.total_trades} trades, "
            f"WR={result.win_rate:.1f}%, PF={result.profit_factor}, "
            f"DD={result.max_drawdown_pct}%"
        )
        return result.to_dict()


def _tf_to_seconds(tf: str) -> int:
    """Convert timeframe string to seconds."""
    mapping = {
        "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
        "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600,
        "12h": 43200, "1d": 86400, "1w": 604800,
    }
    return mapping.get(tf, 3600)
