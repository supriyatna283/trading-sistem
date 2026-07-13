"""Diagnostic: why HYPEUSDT rarely generates signals."""
import asyncio
from app.engines.market_data import MarketDataEngine
from app.engines.confluence import ConfluenceEngine
from app.engines.smart_money import SmartMoneyConceptsEngine
from app.engines.market_structure import MarketStructureAnalyzer
from app.engines.setup_generator import SetupGenerator
from app.engines.mtf_confirmation import MTFConfirmationEngine


async def diagnose(sym: str):
    de = MarketDataEngine()
    ce = ConfluenceEngine(min_confluence_score=12)
    sg = SetupGenerator(min_confluence_score=12, min_rr=1.5)
    mtfe = MTFConfirmationEngine()
    smc_engine = SmartMoneyConceptsEngine()
    st = MarketStructureAnalyzer()

    tfs = ["1d", "4h", "1h", "15m"]
    print(f"\nFetching candles for {sym}...")
    results = await asyncio.gather(*[de.get_candles(sym, tf, 200) for tf in tfs], return_exceptions=True)
    candles = {}
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"  ERROR {tfs[i]}: {r}")
        elif r.empty:
            print(f"  EMPTY {tfs[i]}: no data returned")
        else:
            print(f"  OK    {tfs[i]}: {len(r)} candles, last close={r.iloc[-1]['close']:.4f}")
            candles[tfs[i]] = r

    if not candles:
        print("  FATAL: No candle data at all — source issue (OKX/Binance)")
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
    htf_non_sw = [b for b in htf_biases.values() if b != "SIDEWAYS"]
    dominant = htf_non_sw[0] if htf_non_sw and len(set(htf_non_sw)) == 1 else struct.bias

    print(f"\n{'='*60}")
    print(f"  {sym} | Score={conf.total_score}/{conf.max_score} | Rec={conf.recommendation}")
    print(f"  Entry TF structure bias: {struct.bias}")
    print(f"  Dominant bias (scoring): {dominant}")
    print(f"  HTF biases: {htf_biases}")
    print()

    # Print every scoring criterion
    print("  SCORING BREAKDOWN:")
    for k, v in d.items():
        score = v.get("score", 0) if isinstance(v, dict) else 0
        status = "[+]" if score > 0 else "[ ]"
        key_vals = {kk: vv for kk, vv in v.items() if kk != "score"} if isinstance(v, dict) else v
        print(f"    {status} {k:25s} score={score}  {key_vals}")

    print()
    if setup:
        sl_pct = abs(setup.stop_loss - setup.entry_low) / setup.entry_low * 100 if setup.entry_low else 0
        print(f"  SETUP GENERATED: {setup.direction} | R:R=1:{setup.risk_reward}")
        print(f"    Entry: {setup.entry_low:.4f} - {setup.entry_high:.4f}")
        print(f"    SL: {setup.stop_loss:.4f} ({sl_pct:.2f}%)")
        print(f"    TP1: {setup.take_profit_1:.4f}")
    else:
        print(f"  NO SETUP — checking quality gates...")
        direction = "BUY" if conf.recommendation in ("BUY", "STRONG_BUY") else "SELL"
        print(f"    Recommendation direction: {direction}")

        # Gate 1: min score
        print(f"    Gate 1 (min score 12): {'PASS' if conf.total_score >= 12 else 'FAIL'} ({conf.total_score})")

        # Gate 2: recommendation
        print(f"    Gate 2 (rec != NEUTRAL): {'PASS' if conf.recommendation != 'NEUTRAL' else 'FAIL'} ({conf.recommendation})")

        # Gate 3: HTF
        biases_list = list(htf_biases.values())
        opposite = "BEARISH" if direction == "BUY" else "BULLISH"
        all_opp = all(b == opposite for b in biases_list)
        print(f"    Gate 3 (HTF not all-opposite): {'PASS' if not all_opp else 'FAIL'}")

        # Gate 4: technical anchor
        has_smc = d.get("liquidity", {}).get("swept") or d.get("order_block", {}).get("in_zone")
        has_struct = d.get("structure", {}).get("confirmed")
        has_fvg = d.get("fvg", {}).get("present")
        print(f"    Gate 4 (SMC/struct/FVG anchor): {'PASS' if has_smc or has_struct or has_fvg else 'FAIL'}")
        print(f"      liq_swept={d.get('liquidity',{}).get('swept')} ob_in_zone={d.get('order_block',{}).get('in_zone')} struct={has_struct} fvg={has_fvg}")

        # Gate 5: SL check (approximate)
        print(f"    Gate 5: check setup_generator logs")

    await de.client.aclose()


if __name__ == "__main__":
    asyncio.run(diagnose("HYPEUSDT"))
