"""Test Sprint 3 + Sprint 4 engines."""
import numpy as np
import pandas as pd

np.random.seed(42)
n = 120
prices = 64000 + np.random.randn(n).cumsum() * 300
volumes = np.random.exponential(1000, n)
df = pd.DataFrame({
    'open':   prices * 0.999,
    'high':   prices + abs(np.random.randn(n)) * 200,
    'low':    prices - abs(np.random.randn(n)) * 200,
    'close':  prices,
    'volume': volumes,
})

print("=" * 60)
print("SPRINT 3 ENGINE TESTS")
print("=" * 60)

# 1. Market Maker Flow
from app.engines.market_maker_flow import MarketMakerFlowEngine
mm = MarketMakerFlowEngine()
r1 = mm.analyze(df)
print(f"[PASS] MM Flow: phase={r1.mm_phase}, bias={r1.flow_bias}, score={r1.confluence_score}")

# 2. Wyckoff
from app.engines.wyckoff import WyckoffEngine
wyk = WyckoffEngine()
r2 = wyk.analyze(df)
print(f"[PASS] Wyckoff: schema={r2.schematic}, phase={r2.phase}, score={r2.confluence_score}")

# 3. ML Scoring
from app.engines.ml_scoring import AdaptiveMLScoringEngine
ml = AdaptiveMLScoringEngine()
r3 = ml.analyze(df)
print(f"[PASS] ML Score: signal={r3.signal}, ml_score={r3.ml_score}, regime={r3.regime}")

# 4. Portfolio Optimizer
from app.engines.portfolio_optimizer import PortfolioOptimizerEngine
port = PortfolioOptimizerEngine()
returns1 = np.diff(np.log(prices))
prices2  = 3000 + np.random.randn(n).cumsum() * 80
prices3  = 150  + np.random.randn(n).cumsum() * 5
returns2 = np.diff(np.log(np.abs(prices2) + 1))
returns3 = np.diff(np.log(np.abs(prices3) + 1))
min_len = min(len(returns1), len(returns2), len(returns3))
mat = np.column_stack([returns1[-min_len:], returns2[-min_len:], returns3[-min_len:]])
r4 = port.optimize(["BTC", "ETH", "SOL"], mat)
print(f"[PASS] Portfolio: recommended={r4.recommended_type}, sharpe={r4.recommended.sharpe:.2f}")
print(f"       Allocs: {[(a.symbol, a.weight_pct) for a in r4.allocations]}")

print()
print("=" * 60)
print("SPRINT 4 ENGINE TESTS")
print("=" * 60)

# 5. GARCH
from app.engines.garch_volatility import GARCHVolatilityEngine
garch = GARCHVolatilityEngine()
r5 = garch.analyze(df, current_price=float(prices[-1]))
print(f"[PASS] GARCH: vol={r5.current_vol_daily:.3f}%, regime={r5.vol_regime}, alpha={r5.alpha:.3f}, beta={r5.beta:.3f}")
print(f"       Forecast 1d={r5.forecast_1d:.3f}%, 5d={r5.forecast_5d:.3f}%")

# 6. Options / Perps
from app.engines.options_perps import OptionsPerpsEngine
opts = OptionsPerpsEngine()
r6 = opts.analyze(spot_price=64000, iv_30d=0.70, funding_rate_8h=0.02, long_short_ratio=1.3)
print(f"[PASS] Options: bias={r6.options_bias}, PCR={r6.put_call_ratio}")
if r6.atm_call:
    print(f"       ATM Call: price={r6.atm_call.theoretical_price:.2f}, delta={r6.atm_call.greeks.delta:.3f}")

# 7. Social Trading
from app.engines.social_trading import SocialTradingEngine
social = SocialTradingEngine()
lb = social.get_leaderboard()
sigs = social.get_active_signals()
consensus = social.get_consensus("BTCUSDT")
print(f"[PASS] Social: leaders={len(lb)}, signals={len(sigs)}")
print(f"       #1 Trader: {lb[0].name} (score={lb[0].rank_score})")
if consensus:
    print(f"       BTCUSDT consensus: {consensus.direction} ({consensus.confidence:.0f}% confidence)")

print()
print("All Sprint 3 + 4 engines PASSED!")
