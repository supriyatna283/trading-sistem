import sys
import asyncio
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.services.token_discovery import TokenDiscoveryService
import logging

logging.basicConfig(level=logging.INFO)

async def main():
    db = SessionLocal()
    try:
        discovery = TokenDiscoveryService()
        await discovery.run_discovery(db)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
