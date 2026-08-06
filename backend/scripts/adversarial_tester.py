import asyncio
import os
import json
import logging
from typing import Dict, Any, List

from openai import AsyncOpenAI
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Test Scenarios: 
# All scenarios have PERFECT technical setups (Score 90+ / A+ Grade)
# But they have one fatal fundamental flaw (the "adversarial" injection).
SCENARIOS = [
    {
        "name": "Massive Whale Dump on Bullish TA",
        "signal": "BUY",
        "grade": "A+",
        "score": 95,
        "ta_context": "RSI at 40 (Oversold), MACD Golden Cross, Price at Daily Order Block, Trend is strongly NAIK.",
        "anomaly": "Order Flow Delta shows -85% SELL dominance. 15 Whales just market sold $5M each in the last 5 minutes.",
        "expected_action": "WAIT"
    },
    {
        "name": "Flash Crash News on Bullish TA",
        "signal": "BUY",
        "grade": "A",
        "score": 88,
        "ta_context": "Price sweeping liquidity and closing above FVG. Strong bullish divergence on RSI.",
        "anomaly": "Major Crypto Exchange just announced they are hacked. Sentiment is CRITICAL NEGATIVE.",
        "expected_action": "WAIT"
    },
    {
        "name": "DXY Parabolic Spike on Bullish Crypto",
        "signal": "BUY",
        "grade": "A+",
        "score": 92,
        "ta_context": "Perfect multi-timeframe alignment for LONG. Volume is increasing on green candles.",
        "anomaly": "DXY (US Dollar Index) just spiked +1.5% in 1 hour due to emergency FED rate hike. Extreme risk-off macro environment.",
        "expected_action": "WAIT"
    },
    {
        "name": "Extreme Funding Rate on Bearish TA",
        "signal": "SELL",
        "grade": "A",
        "score": 89,
        "ta_context": "Price broke below 200 EMA, MACD bearish cross. RSI 65.",
        "anomaly": "Funding rate is massively negative (-0.75%). The market is overly short. A massive short squeeze is imminent.",
        "expected_action": "WAIT"
    },
    {
        "name": "Perfect Technicals - No Anomalies (Control Group)",
        "signal": "BUY",
        "grade": "A+",
        "score": 98,
        "ta_context": "Price at key support, RSI oversold, Bullish Engulfing candle.",
        "anomaly": "Market is calm. DXY is stable. Order flow is slightly bullish.",
        "expected_action": "BUY"
    }
]

def build_system_prompt() -> str:
    # This mirrors the aggressive system prompt used in ai_analysis.py
    return """
    You are an elite, highly skeptical Senior Quantitative Trading Analyst.
    Your job is to analyze market data and provide a FINAL TRADING DECISION: BUY, SELL, or WAIT.
    
    CRITICAL RULES (ANCHOR BIAS):
    1. NEVER trust technicals blindly. Technical indicators are lagging and easily manipulated.
    2. If fundamental anomalies (Whale dumps, Macro shocks, Hacks, Extreme Sentiment) contradict the technical setup, you MUST choose WAIT to protect capital.
    3. You must include a <self_critique> block challenging your own analysis before your final verdict.
    4. Your final verdict must be clearly labeled at the end as "VERDICT: [BUY|SELL|WAIT]".
    """

def build_user_prompt(scenario: Dict[str, Any]) -> str:
    return f"""
    Please evaluate this market snapshot:
    
    ENGINE SIGNAL: {scenario['signal']} (Grade: {scenario['grade']}, Score: {scenario['score']}/100)
    
    TECHNICAL CONTEXT:
    {scenario['ta_context']}
    
    FUNDAMENTAL / MACRO CONTEXT:
    {scenario['anomaly']}
    
    What is your decision?
    """

async def run_adversarial_tests():
    settings = get_settings()
    client = AsyncOpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=settings.NVIDIA_API_KEY,
    )
    
    system_prompt = build_system_prompt()
    
    success_count = 0
    total = len(SCENARIOS)
    
    logger.info(f"Starting Adversarial Testing against {total} scenarios...")
    
    for i, s in enumerate(SCENARIOS):
        logger.info(f"\n--- Testing Scenario {i+1}: {s['name']} ---")
        user_prompt = build_user_prompt(s)
        
        try:
            response = await client.chat.completions.create(
                model="nvidia/nemotron-3-ultra-550b-a55b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500,
            )
            
            output = response.choices[0].message.content
            
            # Simple heuristic to extract the verdict
            verdict = "UNKNOWN"
            if "VERDICT: WAIT" in output.upper():
                verdict = "WAIT"
            elif "VERDICT: BUY" in output.upper():
                verdict = "BUY"
            elif "VERDICT: SELL" in output.upper():
                verdict = "SELL"
                
            passed = (verdict == s['expected_action'])
            if passed:
                success_count += 1
                logger.info(f"✅ PASSED (Expected: {s['expected_action']}, Got: {verdict})")
            else:
                logger.error(f"❌ FAILED (Expected: {s['expected_action']}, Got: {verdict})")
                logger.error(f"AI Output snippet:\n{output[-200:]}")
                
        except Exception as e:
            logger.error(f"API Error on scenario {i+1}: {e}")
            
    rejection_rate = (success_count / total) * 100
    logger.info(f"\n=========================================")
    logger.info(f"TESTING COMPLETE. Score: {success_count}/{total} ({rejection_rate:.1f}%)")
    logger.info(f"=========================================")

if __name__ == "__main__":
    asyncio.run(run_adversarial_tests())
