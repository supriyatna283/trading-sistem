import asyncio
import json
from app.routers.market_data import get_historical_candles

async def test():
    res = await get_historical_candles('XRPUSDT', '15m', 5)
    print(json.dumps(res))

asyncio.run(test())
