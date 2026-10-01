import sys
import asyncio
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.whale.scoring.engine import ScoringEngine
from app.whale.providers.auto_provider import AutoWhaleProvider

async def main():
    db = SessionLocal()
    try:
        provider = AutoWhaleProvider()
        engine = ScoringEngine(provider=provider)
        
        # We need to simulate the environment correctly
        print("Scoring QNT...")
        result = await engine.score(
            symbol="QNT",
            chain_id="ethereum",
            token_address="0x4a220e6096b25eadb88358cb44068a3248254675",
            db=db,
            price_change_7d_pct=2.5,
            current_price=105.0
        )
        
        import json
        print(json.dumps(result.to_dict(), indent=2))
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
