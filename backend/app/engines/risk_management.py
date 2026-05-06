"""
Risk Management Engine
=======================
Position sizing, maximum risk, and portfolio exposure calculations.
"""

from app.schemas.risk import PositionSizeRequest, PositionSizeResult, RiskSettingsSchema


class RiskManagementEngine:
    """Calculates position sizes and risk metrics."""

    def calculate_position_size(self, req: PositionSizeRequest) -> PositionSizeResult:
        """Calculate the appropriate position size given risk parameters."""
        risk_amount = req.account_balance * (req.risk_per_trade / 100)

        if req.direction == "BUY":
            stop_distance = abs(req.entry_price - req.stop_loss)
        else:
            stop_distance = abs(req.stop_loss - req.entry_price)

        if stop_distance == 0:
            return PositionSizeResult(
                position_size=0,
                risk_amount=risk_amount,
                stop_distance=0,
                stop_distance_pct=0,
            )

        position_size = risk_amount / stop_distance
        stop_distance_pct = (stop_distance / req.entry_price) * 100

        return PositionSizeResult(
            position_size=round(position_size, 6),
            risk_amount=round(risk_amount, 2),
            stop_distance=round(stop_distance, 8),
            stop_distance_pct=round(stop_distance_pct, 4),
        )

    def calculate_risk_reward(
        self, entry: float, stop_loss: float, take_profit: float, direction: str
    ) -> float:
        """Calculate risk/reward ratio."""
        if direction == "BUY":
            risk = abs(entry - stop_loss)
            reward = abs(take_profit - entry)
        else:
            risk = abs(stop_loss - entry)
            reward = abs(entry - take_profit)

        return round(reward / risk, 2) if risk > 0 else 0

    def check_daily_risk(
        self,
        settings: RiskSettingsSchema,
        current_daily_loss: float,
    ) -> dict:
        """Check if daily risk limit has been reached."""
        max_daily_loss = settings.account_balance * (settings.max_daily_risk / 100)
        remaining = max_daily_loss - abs(current_daily_loss)
        return {
            "max_daily_loss": round(max_daily_loss, 2),
            "current_daily_loss": round(current_daily_loss, 2),
            "remaining_risk": round(max(remaining, 0), 2),
            "limit_reached": remaining <= 0,
        }

    def portfolio_exposure(
        self,
        account_balance: float,
        open_positions: list,
    ) -> dict:
        """Calculate total portfolio exposure."""
        total_risk = sum(p.get("risk_amount", 0) for p in open_positions)
        total_size = sum(p.get("position_value", 0) for p in open_positions)
        return {
            "total_risk": round(total_risk, 2),
            "total_risk_pct": round((total_risk / account_balance) * 100, 2) if account_balance > 0 else 0,
            "total_exposure": round(total_size, 2),
            "exposure_pct": round((total_size / account_balance) * 100, 2) if account_balance > 0 else 0,
            "open_positions_count": len(open_positions),
        }
