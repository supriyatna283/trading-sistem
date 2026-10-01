from app.engines.pd_zones import PDZoneEngine
from app.engines.liquidity_sweep import LiquiditySweepEngine
from app.engines.ob_strength import OBStrengthMeter
from app.engines.position_sizing import PositionSizingEngine
from app.schemas.market_data import OrderBlock
import pandas as pd, numpy as np

print("Testing Sprint 1 Engines...")

# Test data
np.random.seed(42)
prices = 64000 + np.random.randn(30).cumsum() * 200
df_test = pd.DataFrame({
    'open':   prices,
    'high':   prices + 100,
    'low':    prices - 100,
    'close':  prices,
    'volume': np.ones(30) * 1000
})

# 1. PD Zone Engine
pd_eng = PDZoneEngine()
r1 = pd_eng.analyze(df_test, current_price=64500, lookback=20)
print(f"PD Zone Engine OK: zone={r1.zone}, signal={r1.signal}, ote={r1.is_in_ote}")

# 2. Liquidity Sweep
sweep_eng = LiquiditySweepEngine()
r2 = sweep_eng.analyze(df_test)
print(f"Sweep Engine OK: pools={len(r2['pools'])}, sweeps={len(r2['sweeps'])}, score={r2['score']}")

# 3. OB Strength
ob_meter = OBStrengthMeter()
test_ob = OrderBlock(type='BULLISH', high=64200.0, low=63900.0, index=5)
scored = ob_meter.score_order_blocks(df_test, [test_ob])
print(f"OB Strength OK: grade={scored[0].grade}, score={scored[0].score}")

# 4. Position Sizing
size_eng = PositionSizingEngine()
r3 = size_eng.calculate(
    account_balance=10000,
    risk_pct=1.0,
    entry=64000,
    stop_loss=63000,
    direction='BUY',
    win_rate=0.55,
    avg_rr=2.0,
    take_profits=[66000]
)
print(f"Position Sizing OK: size={r3.position_size}, ror={r3.risk_of_ruin_pct}%, kelly={r3.kelly_quarter}%")
print(f"  EV={r3.expected_value}, grade={r3.size_grade}, max_losses={r3.max_consecutive_losses}")

print("")
print("All Sprint 1 engines passed!")
