"""
Whale Scoring Scheduler
========================
Runs periodically in the background to recalculate scores for all
active watchlist coins and trigger alerts if thresholds are met.
"""
import asyncio
import logging
from typing import Callable

from sqlalchemy.orm import Session
from app.whale.scoring.engine import ScoringEngine
from app.whale.scoring.config import load_scoring_config
from app.whale.alert.manager import AlertManager
from app.whale.providers.mock_provider import MockWhaleProvider
from app.whale.providers.hyperliquid_provider import HyperliquidProvider
from app.whale.providers.coingecko_provider import CoinGeckoProvider
from app.models.whale import WatchlistCoin

logger = logging.getLogger(__name__)

async def run_scoring_scheduler(db_factory: Callable[[], Session]):
    """Background task to run scoring periodically (e.g. every 15 mins)."""
    while True:
        try:
            logger.info("🤖 Starting Whale Scoring cycle...")
            db = next(db_factory())
            try:
                # 1. Run Token Discovery
                from app.services.token_discovery import TokenDiscoveryService
                discovery = TokenDiscoveryService()
                await discovery.run_discovery(db)
                
                # 2. Load config and active coins
                config = load_scoring_config()
                coins = db.query(WatchlistCoin).filter_by(is_active=True).all()
                
                if not coins:
                    logger.info("No active coins in watchlist for scoring.")
                else:
                    # 3. Select provider
                    # In a real setup, we might have a composite provider that routes
                    # by chain_id (e.g. hyperliquid -> HL provider, ethereum -> Etherscan)
                    # For now, we use a single instance based on default config
                    from app.whale.providers.auto_provider import AutoWhaleProvider
                    pname = (config.default_provider or "auto").lower()
                    if pname == "hyperliquid":
                        provider = HyperliquidProvider()
                    elif pname == "coingecko":
                        provider = CoinGeckoProvider()
                    elif pname == "auto":
                        provider = AutoWhaleProvider()
                    else:
                        provider = MockWhaleProvider()
                        
                    engine = ScoringEngine(provider=provider, config=config)
                    alert_manager = AlertManager(config=config)

                    # 3. Score each coin
                    from app.routers.whale_scoring import _persist_score
                    for coin in coins:
                        try:
                            result = await engine.score(
                                symbol=coin.symbol,
                                chain_id=coin.chain_id,
                                token_address=coin.token_address or "",
                                db=db,
                            )
                            _persist_score(db, coin.id, result)
                            
                            # Evaluate alerts
                            await alert_manager.evaluate_and_alert(db, coin.id, result)
                            
                            logger.info(f"✅ Scored {coin.symbol}: {result.score:.1f} ({result.grade})")
                        except Exception as e:
                            logger.error(f"❌ Failed to score {coin.symbol}: {e}")
                        
            finally:
                db.close()
                
        except asyncio.CancelledError:
            logger.info("Whale Scoring Scheduler cancelled")
            break
        except Exception as e:
            logger.error(f"Error in Whale Scoring Scheduler: {e}")
            
        # Sleep for 15 minutes before next cycle
        await asyncio.sleep(15 * 60)
