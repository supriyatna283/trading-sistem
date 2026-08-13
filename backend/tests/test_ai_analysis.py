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
    
    # tp1 = 100 + 3 * 2.0 = 106.0
    assert result["tp1"] == 106.0
    
    # tp2 = 100 + 3 * 3.0 = 109.0
    assert result["tp2"] == 109.0

def test_calculate_setup_levels_sell_with_ob_and_liq():
    """Since V6, we use the fallback logic when smc_obj is missing.
    Entry defaults to current price."""
    ctx = {
        "signal": "SELL",
        "price": {"current": 100},
        "atr": 2,
        "smc_detail": {}
    }
    result = _calculate_setup_levels(ctx)
    
    # Fallback sets entry to current price
    assert result["entry_low"] == 100.0
    assert result["entry_high"] == 100.0
    
    # sl_dist = max(atr * 1.5, price * 0.003) = 3.0
    # sl = 100 + 3.0 = 103.0
    assert result["stop_loss"] == 103.0
    
    # risk = 3.0
    # default tp1 = 100 - 3.0 * 2.0 = 94.0
    assert result["tp1"] == 94.0
    
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
