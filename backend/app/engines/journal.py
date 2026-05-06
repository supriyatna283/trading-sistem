"""
Trading Journal Analytics Engine
==================================
Calculates P&L metrics: win rate, profit factor, drawdown, expectancy, etc.
"""

from typing import List
from app.schemas.journal import JournalAnalytics


class JournalAnalyticsEngine:
    """Computes performance analytics from journal entries."""

    def calculate(self, entries: list) -> JournalAnalytics:
        """Calculate analytics from a list of journal entry dicts."""
        if not entries:
            return JournalAnalytics()

        wins = [e for e in entries if e.get("result") == "WIN"]
        losses = [e for e in entries if e.get("result") == "LOSS"]
        breakevens = [e for e in entries if e.get("result") == "BREAKEVEN"]

        total = len(entries)
        win_count = len(wins)
        loss_count = len(losses)
        be_count = len(breakevens)

        win_rate = (win_count / total) * 100 if total > 0 else 0

        # PnL
        pnls = [e.get("pnl", 0) or 0 for e in entries]
        total_pnl = sum(pnls)

        win_pnls = [e.get("pnl", 0) or 0 for e in wins]
        loss_pnls = [e.get("pnl", 0) or 0 for e in losses]

        gross_profit = sum(p for p in win_pnls if p > 0)
        gross_loss = abs(sum(p for p in loss_pnls if p < 0))

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        # R-multiples
        r_multiples = [e.get("r_multiple", 0) or 0 for e in entries]
        avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0

        # Drawdown
        equity_curve = []
        running = 0
        for p in pnls:
            running += p
            equity_curve.append(running)

        max_dd = self._max_drawdown(equity_curve)

        # Averages
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
        avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0

        # Expectancy = (Win% × Avg Win) − (Loss% × Avg Loss)
        win_pct = win_count / total if total > 0 else 0
        loss_pct = loss_count / total if total > 0 else 0
        expectancy = (win_pct * avg_win) - (loss_pct * abs(avg_loss))

        best = max(pnls) if pnls else 0
        worst = min(pnls) if pnls else 0

        return JournalAnalytics(
            total_trades=total,
            wins=win_count,
            losses=loss_count,
            breakeven=be_count,
            win_rate=round(win_rate, 2),
            profit_factor=round(profit_factor, 2),
            avg_r_multiple=round(avg_r, 2),
            total_pnl=round(total_pnl, 2),
            max_drawdown=round(max_dd, 2),
            expectancy=round(expectancy, 2),
            best_trade=round(best, 2),
            worst_trade=round(worst, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
        )

    @staticmethod
    def _max_drawdown(equity: List[float]) -> float:
        """Calculate max drawdown from equity curve."""
        if not equity:
            return 0.0
        peak = equity[0]
        max_dd = 0.0
        for val in equity:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
        return max_dd
