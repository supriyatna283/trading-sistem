
import asyncio
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.engines.market_data import MarketDataEngine
from app.engines.scanner import MarketScanner

async def test_engines():
    print("--- Testing Binance Fetching (Primary) ---")
    engine = MarketDataEngine()
    try:
        df = await engine.fetch_binance_candles("BTCUSDT", "1h", 10)
        print(f"Binance Candles fetched: {len(df)}")
        if not df.empty:
            print(df.head(2))
        else:
            print("ERROR: Binance Candles DF is empty!")
    except Exception as e:
        print(f"Exception in Binance fetch: {e}")

    print("\n--- Testing get_candles fallback ---")
    scanner = MarketScanner()
    try:
        results = await scanner.scan(symbols=["BTCUSDT", "ETHUSDT"])
        print(f"Scanner results: {len(results)}")
        for r in results:
            print(f"- {r['symbol']}: {r['trend']}, Confluence: {r['confluence_score']}")
    except Exception as e:
        print(f"Exception in MarketScanner: {e}")

if __name__ == "__main__":
    asyncio.run(test_engines())
