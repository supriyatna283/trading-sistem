import pytest
from app.routers.ai_analysis import _calculate_setup_levels

def test_calculate_setup_levels_wait():
    ctx = {
        "signal": "WAIT",
        "price": {"current": 50000},
        "atr": 100,
        "smc_detail": {}
    }
    result = _calculate_setup_levels(ctx)
    assert result["entry_low"] is None
    assert result["entry_high"] is None
    assert result["stop_loss"] is None
    assert result["tp1"] is None
    assert result["risk_reward"] is None

def test_calculate_setup_levels_buy_default():
    ctx = {
        "signal": "BUY",
        "price": {"current": 100},
        "atr": 2,
        "smc_detail": {}
    }
    result = _calculate_setup_levels(ctx)
    assert result["entry_low"] == 100
    assert result["entry_high"] == 100
    
    # sl_dist = max(atr * 1.5, price * 0.003)
    # atr * 1.5 = 3
    # price * 0.003 = 0.3
    # sl_dist = 3. SL = 100 - 3 = 97
    assert result["stop_loss"] == 97.0
    
    # risk = abs(100 - 97) = 3
    # tp1 = 100 + 3 * 1.8 = 105.4
    assert result["tp1"] == 105.4
    
    # tp2 = 100 + 3 * 3.0 = 109.0
    assert result["tp2"] == 109.0

def test_calculate_setup_levels_sell_with_ob_and_liq():
    ctx = {
        "signal": "SELL",
        "price": {"current": 100},
        "atr": 2,
        "smc_detail": {
            "order_blocks": [
                {"type": "BEARISH", "low": 102, "high": 105},
                {"type": "BULLISH", "low": 90, "high": 95}
            ],
            "liquidity_prices": [105, 95, 90, 80]
        }
    }
    result = _calculate_setup_levels(ctx)
    
    # Nearest Bearish OB above 100 is the one at 102-105.
    assert result["entry_low"] == 102
    assert result["entry_high"] == 105
    
    # sl_dist = nearest["high"] - price + atr * 0.3
    # sl_dist = 105 - 100 + 2 * 0.3 = 5 + 0.6 = 5.6
    # sl = 100 + 5.6 = 105.6
    assert result["stop_loss"] == 105.6
    
    # risk = abs(100 - 105.6) = 5.6
    # default tp1 = 100 - 5.6 * 1.8 = 89.92
    # below_liq = [95, 90, 80]
    # liq 0 = 95. Distance from 89.92 = abs(95 - 89.92) / 100 = 5.08 / 100 = 0.0508 > 0.03 (no snap)
    assert result["tp1"] == 89.92
    
def test_calculate_setup_levels_buy_with_liq_snap():
    ctx = {
        "signal": "BUY",
        "price": {"current": 100},
        "atr": 2,
        "smc_detail": {
            "liquidity_prices": [106]  # should snap tp1 if within 3% of 105.4
        }
    }
    result = _calculate_setup_levels(ctx)
    
    # Default TP1 is 105.4.
    # Liquidity at 106. Distance: abs(106 - 105.4) / 100 = 0.6 / 100 = 0.006 < 0.03.
    # So TP1 should snap to 106.
    assert result["tp1"] == 106.0
