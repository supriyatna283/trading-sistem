import logging
import asyncio
import aiohttp
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.whale import WatchlistCoin, WhaleTransaction, Wallet
from app.whale.providers.auto_provider import AutoWhaleProvider

logger = logging.getLogger(__name__)

class TokenDiscoveryService:
    """
    Auto Token Discovery (Alpha Hunter)
    ===================================
    Automatically finds and adds new promising tokens to the Watchlist 
    so the Scoring Engine can analyze them.
    
    Methods:
      1. discover_trending_coingecko: Fetches top trending coins from CG.
      2. discover_smart_money_tokens: Finds tokens actively traded by Smart Wallets.
    """
    
    def __init__(self):
        self.cg_trending_url = "https://api.coingecko.com/api/v3/search/trending"

    async def discover_trending_coingecko(self, db: Session) -> int:
        """Fetch trending coins from CoinGecko and add to Watchlist."""
        added_count = 0
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.cg_trending_url, timeout=10) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch CG trending: {response.status}")
                        return 0
                    
                    data = await response.json()
                    
                    # Get existing symbols to avoid DB unique constraint errors
                    existing_symbols = {
                        row[0].upper() for row in db.query(WatchlistCoin.symbol).all()
                    }

                    coins = data.get("coins", [])
                    for item in coins:
                        coin = item.get("item", {})
                        symbol = coin.get("symbol", "").upper()
                        
                        if not symbol or symbol in existing_symbols:
                            continue
                            
                        # Add to watchlist (default chain to 'ethereum' for CG trending if unknown)
                        # In production, you might map platform IDs to chain_ids
                        new_coin = WatchlistCoin(
                            symbol=symbol,
                            chain_id="ethereum", 
                            coingecko_id=coin.get("id"),
                            is_active=True,
                            notes="Auto-discovered via CoinGecko Trending"
                        )
                        db.add(new_coin)
                        existing_symbols.add(symbol)
                        added_count += 1
                        
            if added_count > 0:
                db.commit()
                logger.info(f"Added {added_count} trending coins to watchlist.")
                
        except Exception as e:
            logger.error(f"Error in discover_trending_coingecko: {e}")
            db.rollback()
            
        return added_count

    async def discover_smart_money_tokens(self, db: Session) -> int:
        """Find tokens that Smart Wallets are accumulating in our DB."""
        added_count = 0
        try:
            # 1. Get existing watchlist symbols
            existing_symbols = {
                row[0].upper() for row in db.query(WatchlistCoin.symbol).all()
            }
            
            # 2. Query tokens transacted by smart_money wallets in the last 7 days
            from datetime import timedelta
            since = datetime.now(timezone.utc) - timedelta(days=7)
            
            # Subquery: get all smart money wallet IDs
            from sqlalchemy import select
            smart_wallet_ids = select(Wallet.id).where(Wallet.entity_type == "smart_money")
            
            # Query transactions involving these wallets
            new_tokens = (
                db.query(
                    WhaleTransaction.token_symbol, 
                    WhaleTransaction.chain_id, 
                    WhaleTransaction.token_address
                )
                .filter(
                    WhaleTransaction.block_time >= since,
                    (WhaleTransaction.from_wallet_id.in_(smart_wallet_ids)) | 
                    (WhaleTransaction.to_wallet_id.in_(smart_wallet_ids))
                )
                .group_by(
                    WhaleTransaction.token_symbol, 
                    WhaleTransaction.chain_id, 
                    WhaleTransaction.token_address
                )
                .all()
            )
            
            for symbol, chain_id, token_address in new_tokens:
                sym_upper = symbol.upper()
                if sym_upper not in existing_symbols:
                    new_coin = WatchlistCoin(
                        symbol=sym_upper,
                        chain_id=chain_id or "ethereum",
                        token_address=token_address,
                        is_active=True,
                        notes="Auto-discovered via Smart Money Activity"
                    )
                    db.add(new_coin)
                    existing_symbols.add(sym_upper)
                    added_count += 1
                    
            if added_count > 0:
                db.commit()
                logger.info(f"Added {added_count} smart money tokens to watchlist.")
                
        except Exception as e:
            logger.error(f"Error in discover_smart_money_tokens: {e}")
            db.rollback()
            
        return added_count

    async def run_discovery(self, db: Session):
        """Run all discovery methods."""
        logger.info("Starting Auto Token Discovery...")
        
        # Run concurrently
        task1 = self.discover_trending_coingecko(db)
        task2 = self.discover_smart_money_tokens(db)
        
        results = await asyncio.gather(task1, task2, return_exceptions=True)
        
        trending_count = results[0] if isinstance(results[0], int) else 0
        smart_count = results[1] if isinstance(results[1], int) else 0
        
        total = trending_count + smart_count
        logger.info(f"Auto Token Discovery finished. Added {total} new tokens.")
        return total
