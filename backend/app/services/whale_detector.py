import asyncio
import logging
from typing import Callable
from sqlalchemy.orm import Session
import httpx

# We will use web3 for EVM. Note: Make sure web3 is in requirements.txt
from web3 import AsyncWeb3, AsyncHTTPProvider
try:
    from web3.middleware import ExtraDataToPOAMiddleware
except ImportError:
    from web3.middleware import async_geth_poa_middleware as ExtraDataToPOAMiddleware

from app.models.whale import WhaleTransaction, WhaleThreshold, WhaleDirection
from app.schemas.whale import WhaleTransactionResponse
from app.services.wallet_labeler import enrich_wallet
from app.services.websocket_manager import ws_manager
from app.config import get_settings
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
settings = get_settings()

_polling_tasks = []

async def get_eth_price() -> float:
    """Mock/Simplified fetch of ETH price for USD value calculation."""
    # In a real app, use Binance or OKX ticker API or Pyth
    # We will just hardcode an approximation for demo of free polling
    return 3000.0

async def get_bnb_price() -> float:
    return 500.0

async def get_sol_price() -> float:
    return 150.0

async def poll_evm_chain(chain_id: str, rpc_url: str, db_factory: Callable[[], Session], get_price: Callable):
    """Background task to poll an EVM chain via Public RPC."""
    logger.info(f"Starting {chain_id} RPC polling on {rpc_url}")
    
    # Initialize async web3 provider
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    last_block = None
    
    while True:
        try:
            # Check connection
            # if not await w3.is_connected():
            #     logger.error(f"{chain_id} RPC disconnected. Retrying in 10s...")
            #     await asyncio.sleep(10)
            #     continue

            current_block = await w3.eth.block_number
            
            if last_block is None:
                last_block = current_block - 1
                
            if current_block > last_block:
                # We process block by block
                block_to_process = last_block + 1
                block = await w3.eth.get_block(block_to_process, full_transactions=True)
                
                # Fetch threshold and price
                db = next(db_factory())
                try:
                    threshold_entry = db.query(WhaleThreshold).filter_by(chain_id=chain_id).first()
                    usd_threshold = threshold_entry.usd_threshold if threshold_entry else 500000.0
                    token_price = await get_price()
                    min_amount = usd_threshold / token_price

                    for tx in block.transactions:
                        # We only track native transfers (ETH/BNB) for this free public polling 
                        # to avoid heavy receipt/log parsing limits.
                        value_wei = tx.value
                        if value_wei == 0:
                            continue
                            
                        amount = float(w3.from_wei(value_wei, 'ether'))
                        usd_value = amount * token_price
                        
                        if usd_value >= usd_threshold:
                            tx_hash = tx.hash.hex()
                            existing = db.query(WhaleTransaction).filter_by(chain_id=chain_id, tx_hash=tx_hash).first()
                            if existing:
                                continue
                                
                            from_wallet = await enrich_wallet(db, chain_id, tx["from"])
                            to_wallet = await enrich_wallet(db, chain_id, tx.to) if tx.to else await enrich_wallet(db, chain_id, "Contract Creation")
                            
                            direction = WhaleDirection.TRANSFER
                            if from_wallet.entity_type == "exchange":
                                direction = WhaleDirection.OUTFLOW
                            elif to_wallet.entity_type == "exchange":
                                direction = WhaleDirection.INFLOW

                            whale_tx = WhaleTransaction(
                                chain_id=chain_id,
                                tx_hash=tx_hash,
                                from_wallet_id=from_wallet.id,
                                to_wallet_id=to_wallet.id,
                                token_symbol="ETH" if chain_id == "ethereum" else "BNB",
                                token_address="Native",
                                amount=amount,
                                usd_value=usd_value,
                                direction=direction,
                                block_time=datetime.fromtimestamp(block.timestamp, tz=timezone.utc),
                                raw_source="public_rpc"
                            )
                            db.add(whale_tx)
                            db.commit()
                            db.refresh(whale_tx)
                            
                            response = WhaleTransactionResponse.from_orm(whale_tx)
                            await ws_manager.broadcast("whale", response.json())
                            logger.info(f"[{chain_id.upper()} WHALE] {usd_value} USD")
                finally:
                    db.close()
                    
                last_block = block_to_process
                
            # Avoid hammering public RPCs
            await asyncio.sleep(5)
            
        except asyncio.CancelledError:
            logger.info(f"Stopping {chain_id} poller")
            break
        except Exception as e:
            logger.error(f"Error polling {chain_id}: {e}")
            await asyncio.sleep(10) # Backoff on error

async def poll_solana_chain(rpc_url: str, db_factory: Callable[[], Session]):
    """Background task to poll Solana via Public RPC."""
    logger.info(f"Starting solana RPC polling on {rpc_url}")
    
    last_slot = None
    chain_id = "solana"
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # 1. Get current slot
                resp = await client.post(
                    rpc_url, 
                    json={"jsonrpc": "2.0", "id": 1, "method": "getSlot"},
                    timeout=10.0
                )
                
                if resp.status_code == 200:
                    current_slot = resp.json().get("result")
                    
                    if current_slot and last_slot and current_slot > last_slot:
                        # 2. Get block for the slot
                        # Note: Public Solana RPCs heavily rate limit getBlock with full txs. 
                        # We use maxSupportedTransactionVersion=0
                        block_resp = await client.post(
                            rpc_url,
                            json={
                                "jsonrpc": "2.0", 
                                "id": 1, 
                                "method": "getBlock",
                                "params": [
                                    current_slot, 
                                    {"encoding": "json", "transactionDetails": "full", "maxSupportedTransactionVersion": 0}
                                ]
                            }
                        )
                        
                        if block_resp.status_code == 200:
                            block_data = block_resp.json().get("result")
                            if block_data and "transactions" in block_data:
                                db = next(db_factory())
                                try:
                                    threshold_entry = db.query(WhaleThreshold).filter_by(chain_id=chain_id).first()
                                    usd_threshold = threshold_entry.usd_threshold if threshold_entry else 500000.0
                                    sol_price = await get_sol_price()
                                    
                                    for tx in block_data["transactions"]:
                                        # Simple SOL transfer detection (very naive for solana due to complexity of accounts)
                                        meta = tx.get("meta")
                                        if not meta or meta.get("err"):
                                            continue
                                            
                                        pre_balances = meta.get("preBalances", [])
                                        post_balances = meta.get("postBalances", [])
                                        
                                        if not pre_balances or not post_balances:
                                            continue
                                            
                                        # Find largest balance change
                                        max_diff = 0
                                        sender_idx = -1
                                        for i in range(len(pre_balances)):
                                            diff = pre_balances[i] - post_balances[i]
                                            if diff > max_diff:
                                                max_diff = diff
                                                sender_idx = i
                                                
                                        amount_sol = max_diff / 1e9 # Lamports to SOL
                                        usd_value = amount_sol * sol_price
                                        
                                        if usd_value >= usd_threshold and sender_idx >= 0:
                                            tx_hash = tx["transaction"]["signatures"][0]
                                            
                                            existing = db.query(WhaleTransaction).filter_by(chain_id=chain_id, tx_hash=tx_hash).first()
                                            if existing:
                                                continue
                                                
                                            accounts = tx["transaction"]["message"]["accountKeys"]
                                            sender_address = accounts[sender_idx] if type(accounts[0]) == str else accounts[sender_idx]["pubkey"]
                                            
                                            # We just mock the receiver as 'unknown' for this simplified public free approach
                                            from_wallet = await enrich_wallet(db, chain_id, sender_address)
                                            to_wallet = await enrich_wallet(db, chain_id, "Unknown Receiver")
                                            
                                            direction = WhaleDirection.OUTFLOW if from_wallet.entity_type == "exchange" else WhaleDirection.TRANSFER

                                            whale_tx = WhaleTransaction(
                                                chain_id=chain_id,
                                                tx_hash=tx_hash,
                                                from_wallet_id=from_wallet.id,
                                                to_wallet_id=to_wallet.id,
                                                token_symbol="SOL",
                                                token_address="Native",
                                                amount=amount_sol,
                                                usd_value=usd_value,
                                                direction=direction,
                                                block_time=datetime.now(timezone.utc),
                                                raw_source="public_rpc"
                                            )
                                            db.add(whale_tx)
                                            db.commit()
                                            db.refresh(whale_tx)
                                            
                                            response = WhaleTransactionResponse.from_orm(whale_tx)
                                            await ws_manager.broadcast("whale", response.json())
                                            logger.info(f"[SOLANA WHALE] {usd_value} USD")
                                            
                                finally:
                                    db.close()
                                    
                    last_slot = current_slot
                    
            except asyncio.CancelledError:
                logger.info("Stopping solana poller")
                break
            except Exception as e:
                # Silently catch rate limits or network issues to avoid log spam on free RPCs
                # logger.debug(f"Solana poll issue: {e}")
                pass
                
            await asyncio.sleep(8) # Solana blocks are fast, but we don't want to get banned

def start_whale_pollers(db_factory: Callable[[], Session]):
    """Start all chain pollers as asyncio background tasks."""
    global _polling_tasks
    
    if settings.ETH_RPC_URL:
        _polling_tasks.append(asyncio.create_task(poll_evm_chain("ethereum", settings.ETH_RPC_URL, db_factory, get_eth_price)))
        
    if settings.BSC_RPC_URL:
        _polling_tasks.append(asyncio.create_task(poll_evm_chain("bsc", settings.BSC_RPC_URL, db_factory, get_bnb_price)))
        
    if settings.SOL_RPC_URL:
        _polling_tasks.append(asyncio.create_task(poll_solana_chain(settings.SOL_RPC_URL, db_factory)))

def stop_whale_pollers():
    """Cancel all polling tasks."""
    for task in _polling_tasks:
        task.cancel()
    _polling_tasks.clear()
