"""Quick diagnostic: test signal generation for major pairs."""
import asyncio
from app.engines.market_data import MarketDataEngine
from app.engines.confluence import ConfluenceEngine
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.setup_generator import SetupGenerator
from app.engines.mtf_confirmation import MTFConfirmationEngine


async def test(sym):
    de = MarketDataEngine()
    ce = ConfluenceEngine(min_confluence_score=12)
    sg = SetupGenerator(min_confluence_score=12, min_rr=1.5)
    mtfe = MTFConfirmationEngine()
    smc_engine = SmartMoneyConceptsEngine()
    st = MarketStructureAnalyzer()

    tfs = ["1d", "4h", "1h", "15m"]
    results = await asyncio.gather(*[de.get_candles(sym, tf, 200) for tf in tfs], return_exceptions=True)
    candles = {tfs[i]: r for i, r in enumerate(results) if not isinstance(r, Exception) and not r.empty}

    if not candles:
        print(f"{sym}: NO DATA")
        return

    _e = candles.get("1h")
    entry_df = _e if (_e is not None and not _e.empty) else next(iter(candles.values()))
    mtf = mtfe.analyze(candles, sym)
    conf = ce.score(candles, sym, "1h")
    smc_res = smc_engine.analyze(entry_df, sym, "1h")
    struct = st.analyze(entry_df, sym, "1h")
    setup = sg.generate(sym, "1h", conf, smc_res, struct, entry_df, mtf_result=mtf)

    d = conf.details
    htf_biases = d.get("htf_bias", {}).get("biases", {})
    ob = d.get("order_block", {})
    liq = d.get("liquidity", {})
    structure = d.get("structure", {})
    fvg = d.get("fvg", {})

    print(f"\n{'='*55}")
    print(f"  {sym} | Score={conf.total_score}/{conf.max_score} | Rec={conf.recommendation}")
    print(f"  HTF biases: {htf_biases}")
    print(f"  OB in zone: {ob.get('in_zone')} | OB count (fresh): {ob.get('count', 0)}")
    print(f"  Liq swept : {liq.get('swept')} (count={liq.get('swept_count', 0)})")
    print(f"  Structure : {structure.get('confirmed')} bias={structure.get('bias')}")
    print(f"  FVG present: {fvg.get('present')} (count={fvg.get('aligned_count', 0)})")
    print(f"  RSI={d.get('rsi', {}).get('value')} EMA={d.get('ema', {}).get('aligned')} MACD={d.get('macd', {}).get('aligned')}")
    print(f"  StochRSI k={d.get('stoch_rsi', {}).get('k')} d={d.get('stoch_rsi', {}).get('d')} ok={d.get('stoch_rsi', {}).get('aligned')}")
    if setup:
        print(f"  ✅ SETUP GENERATED: {setup.direction} R:R=1:{setup.risk_reward} Entry={round(setup.entry_low,2)}-{round(setup.entry_high,2)} SL={round(setup.stop_loss,2)}")
        sl_pct = abs(setup.stop_loss - setup.entry_low) / setup.entry_low * 100
        print(f"     SL distance: {sl_pct:.2f}%  Type: {setup.setup_type}")
    else:
        print(f"  [REJECTED]")


async def main():
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    tasks = [test(s) for s in symbols]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
