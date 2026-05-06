import asyncio
import logging
import pandas as pd
from app.routers.setups import setup_gen
from app.engines.market_data import MarketDataEngine
from app.engines.mtf_confirmation import MTFConfirmationEngine
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.confluence import ConfluenceEngine

logging.basicConfig(level=logging.ERROR)

async def test_btc():
    md = MarketDataEngine()
    smc_eng = SmartMoneyConceptsEngine()
    mkt_eng = MarketStructureAnalyzer()
    conf_eng = ConfluenceEngine()
    mtf_eng = MTFConfirmationEngine()
    
    symbol = 'BTCUSDT'
    entry_tf = '1h'
    timeframes = ["1d", "4h", "1h", "15m", "5m"]
    
    print(f'--- ANALYZING {symbol} ---')
    
    # 1. Fetch candles for all TFs
    candles_by_tf = {}
    for tf in timeframes:
        print(f'Fetching {tf}...')
        df = await md.get_candles(symbol, tf, limit=300)
        if not df.empty:
            candles_by_tf[tf] = df
    
    if entry_tf not in candles_by_tf:
        print(f'Error: Could not fetch {entry_tf} candles.')
        return
        
    df_entry = candles_by_tf[entry_tf]
    
    # 2. MTF Analysis
    print('\nChecking MTF...')
    mtf_result = mtf_eng.analyze(candles_by_tf, symbol)
    print(f"MTF Dominant Bias: {mtf_result['dominant_bias']}")
    print(f"MTF Confirmed: {mtf_result['confirmed']} ({mtf_result['confirmation_level']})")
    
    # 3. Entry TF Analysis - Confluence score handles internal calls
    print('\nScoring Confluence...')
    conf = conf_eng.score(candles_by_tf, symbol, entry_tf, None, None, mtf_result)
    print(f'Confluence Score: {conf.total_score} / {conf.max_score}')
    print('Scoring Details:')
    for k, v in conf.details.items():
        print(f'  - {k}: {v.get("score", 0)} points')
        if k == "volume" and v.get("score", 0) == 0:
            vol = df_entry["volume"].tail(20).astype(float)
            avg = vol.mean()
            last = vol.iloc[-1]
            print(f"    (Volume Debug: Last={last:.0f}, Avg={avg:.0f}, Ratio={last/avg:.2f}x. Threshold is 2.0x)")
    
    # Need SMC and Structure for the generate call specifically
    structure = mkt_eng.analyze(df_entry, symbol, entry_tf)
    smc = smc_eng.analyze(df_entry, symbol, entry_tf)

    # 4. Setup Generation
    print('\nAttempting Setup Generation...')
    setup = setup_gen.generate(symbol, entry_tf, conf, smc, structure, df_entry, mtf_result, None, None)
    
    print('\n--- RESULT ---')
    if setup:
        print(f'✅ SETUP GENERATED: {setup.direction} at {setup.entry_high}')
    else:
        print('❌ SETUP REJECTED.')
        
    # Manual trace of gates
    print('\n--- Manual Logic Trace ---')
    last_price = float(df_entry.iloc[-1]['close'])
    entry_low, entry_high, sl, tp1, tp2, tp3 = setup_gen._calculate_levels(
            structure.bias, last_price, smc, df_entry
        )
    sl_dist = abs(sl - last_price) / last_price * 100
    print(f'1. SL Distance: {sl_dist:.2f}%. Max for BTC={3.0 if symbol in ["BTCUSDT", "ETHUSDT"] else 5.0}%')
    if sl_dist > (3.0 if symbol in ["BTCUSDT", "ETHUSDT"] else 5.0):
        print("   -> FAIL: SL too far.")
        
    risk = abs(entry_low - sl) if structure.bias == "BULLISH" else abs(sl - entry_high)
    reward = abs(tp1 - entry_high) if structure.bias == "BULLISH" else abs(entry_low - tp1)
    rr = reward / risk if risk > 0 else 0
    print(f'2. R:R Ratio: {rr:.2f}. Min required: {setup_gen.min_rr}')
    if rr < setup_gen.min_rr:
        print("   -> FAIL: R:R too low.")

if __name__ == "__main__":
    asyncio.run(test_btc())
