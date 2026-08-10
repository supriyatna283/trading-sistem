import asyncio
import logging
from typing import Callable, Dict, Any
from sqlalchemy.orm import Session
import httpx
import time

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

# --- Token Cache ---
# Cache structure: { chain_id: { token_address: { 'symbol': 'USDT', 'decimals': 6, 'price_usd': 1.0, 'updated_at': timestamp } } }
TOKEN_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 300  # 5 minutes

ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]

async def get_token_info(chain_id: str, token_address: str, w3: AsyncWeb3 = None) -> dict:
    """Fetch token symbol, decimals, and USD price with caching."""
    if chain_id not in TOKEN_CACHE:
        TOKEN_CACHE[chain_id] = {}
        
    token_address = token_address.lower()
    cached = TOKEN_CACHE[chain_id].get(token_address)
    now = time.time()
    
    if cached and (now - cached['updated_at']) < CACHE_TTL:
        return cached

    # Fetch from DexScreener
    dex_chain_id = chain_id
    if chain_id == 'ethereum':
        dex_chain_id = 'ethereum'
    elif chain_id == 'bsc':
        dex_chain_id = 'bsc'
    elif chain_id == 'solana':
        dex_chain_id = 'solana'
        
    price_usd = 0.0
    symbol = "UNKNOWN"
    decimals = 18 if chain_id != 'solana' else 9 # Safe defaults
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.dexscreener.com/latest/dex/tokens/{token_address}", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                pairs = data.get("pairs", [])
                if pairs:
                    # Sort by liquidity/volume to get best pair
                    best_pair = pairs[0]
                    price_usd = float(best_pair.get("priceUsd", 0.0))
                    
                    if chain_id == 'solana':
                        # DexScreener gives baseToken symbol
                        symbol = best_pair.get("baseToken", {}).get("symbol", "UNKNOWN")
    except Exception as e:
        logger.debug(f"Failed to fetch DexScreener price for {token_address}: {e}")

    # For EVM, try to get decimals and symbol from contract if not on DexScreener or to be precise
    if chain_id in ['ethereum', 'bsc'] and w3:
        try:
            checksum_addr = w3.to_checksum_address(token_address)
            contract = w3.eth.contract(address=checksum_addr, abi=ERC20_ABI)
            # Only fetch if we don't know it yet
            if not cached or 'decimals' not in cached:
                decimals = await contract.functions.decimals().call()
            if symbol == "UNKNOWN":
                try:
                    symbol = await contract.functions.symbol().call()
                except:
                    pass
        except Exception as e:
            logger.debug(f"Failed to read contract {token_address}: {e}")
            
    info = {
        'symbol': symbol,
        'decimals': decimals,
        'price_usd': price_usd,
        'updated_at': now
    }
    TOKEN_CACHE[chain_id][token_address] = info
    return info

async def poll_evm_chain(chain_id: str, rpc_url: str, db_factory: Callable[[], Session]):
    """Background task to poll an EVM chain via Public RPC."""
    logger.info(f"Starting {chain_id} RPC polling on {rpc_url} (All Tokens)")
    
    w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    last_block = None
    
    native_symbol = "ETH" if chain_id == "ethereum" else "BNB"
    
    while True:
        try:
            current_block = await w3.eth.block_number
            if last_block is None:
                last_block = current_block - 1
                
            if current_block > last_block:
                block_to_process = last_block + 1
                block = await w3.eth.get_block(block_to_process, full_transactions=True)
                
                # Get Native Price
                # Use WETH/WBNB address for DexScreener
                weth_addr = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" if chain_id == "ethereum" else "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
                native_info = await get_token_info(chain_id, weth_addr, w3)
                native_price = native_info.get('price_usd', 3000.0 if chain_id == 'ethereum' else 500.0)
                
                db = next(db_factory())
                try:
                    threshold_entry = db.query(WhaleThreshold).filter_by(chain_id=chain_id).first()
                    base_threshold = threshold_entry.usd_threshold if threshold_entry else 10000.0
                    usd_threshold = min(base_threshold, 10000.0)

                    # 1. Process Native Transfers
                    for tx in block.transactions:
                        value_wei = tx.value
                        if value_wei == 0:
                            continue
                            
                        amount = float(w3.from_wei(value_wei, 'ether'))
                        usd_value = amount * native_price
                        
                        if usd_value >= usd_threshold:
                            await process_transaction(
                                db, chain_id, tx.hash.hex(), tx["from"], tx.to or "Contract Creation",
                                native_symbol, "Native", amount, usd_value, block.timestamp
                            )

                    # 2. Process ERC-20 Transfers
                    logs = await w3.eth.get_logs({
                        "fromBlock": block_to_process,
                        "toBlock": block_to_process,
                        "topics": [ERC20_TRANSFER_TOPIC]
                    })
                    
                    for log in logs:
                        # Must have 3 topics: signature, from, to
                        if len(log.topics) == 3:
                            token_address = log.address
                            from_addr = "0x" + log.topics[1].hex()[26:]
                            to_addr = "0x" + log.topics[2].hex()[26:]
                            try:
                                amount_raw = int(log.data.hex(), 16)
                            except ValueError:
                                continue
                                
                            if amount_raw == 0:
                                continue
                                
                            # Fetch token info (cached)
                            token_info = await get_token_info(chain_id, token_address, w3)
                            price_usd = token_info.get('price_usd', 0)
                            
                            # If we don't have a price, we can't calculate whale size
                            if price_usd <= 0:
                                continue
                                
                            decimals = token_info.get('decimals', 18)
                            amount = amount_raw / (10 ** decimals)
                            usd_value = amount * price_usd
                            
                            if usd_value >= usd_threshold:
                                await process_transaction(
                                    db, chain_id, log.transactionHash.hex(), from_addr, to_addr,
                                    token_info.get('symbol', 'UNKNOWN'), token_address, amount, usd_value, block.timestamp
                                )

                finally:
                    db.close()
                    
                last_block = block_to_process
                
            await asyncio.sleep(3)
            
        except asyncio.CancelledError:
            logger.info(f"Stopping {chain_id} poller")
            break
        except Exception as e:
            logger.error(f"Error polling {chain_id}: {e}")
            await asyncio.sleep(5)

async def poll_solana_chain(rpc_url: str, db_factory: Callable[[], Session]):
    """Background task to poll Solana via Public RPC (All Tokens)."""
    logger.info(f"Starting solana RPC polling on {rpc_url}")
    
    last_slot = None
    chain_id = "solana"
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.post(
                    rpc_url, 
                    json={"jsonrpc": "2.0", "id": 1, "method": "getSlot"},
                    timeout=10.0
                )
                
                if resp.status_code == 200:
                    current_slot = resp.json().get("result")
                    
                    if current_slot and last_slot and current_slot > last_slot:
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
                                    usd_threshold = min(threshold_entry.usd_threshold if threshold_entry else 10000.0, 10000.0)
                                    
                                    # Native SOL price
                                    wsol_addr = "So11111111111111111111111111111111111111112"
                                    native_info = await get_token_info(chain_id, wsol_addr)
                                    sol_price = native_info.get('price_usd', 150.0)
                                    
                                    for tx in block_data["transactions"]:
                                        meta = tx.get("meta")
                                        if not meta or meta.get("err"):
                                            continue
                                            
                                        tx_hash = tx["transaction"]["signatures"][0]
                                        block_time = block_data.get("blockTime", int(time.time()))
                                            
                                        # 1. Native SOL Transfers
                                        pre_balances = meta.get("preBalances", [])
                                        post_balances = meta.get("postBalances", [])
                                        if pre_balances and post_balances:
                                            max_diff = 0
                                            sender_idx = -1
                                            for i in range(len(pre_balances)):
                                                diff = pre_balances[i] - post_balances[i]
                                                if diff > max_diff:
                                                    max_diff = diff
                                                    sender_idx = i
                                                    
                                            amount_sol = max_diff / 1e9
                                            usd_value = amount_sol * sol_price
                                            
                                            if usd_value >= usd_threshold and sender_idx >= 0:
                                                accounts = tx["transaction"]["message"]["accountKeys"]
                                                sender_address = accounts[sender_idx] if type(accounts[0]) == str else accounts[sender_idx]["pubkey"]
                                                await process_transaction(
                                                    db, chain_id, tx_hash, sender_address, "Unknown Receiver",
                                                    "SOL", "Native", amount_sol, usd_value, block_time
                                                )

                                        # 2. SPL Token Transfers
                                        pre_token_balances = meta.get("preTokenBalances", [])
                                        post_token_balances = meta.get("postTokenBalances", [])
                                        
                                        # Group by mint (token address)
                                        mint_diffs = {} # accountIndex -> { mint -> diff }
                                        
                                        for ptb in post_token_balances:
                                            idx = ptb["accountIndex"]
                                            mint = ptb["mint"]
                                            amount = float(ptb.get("uiTokenAmount", {}).get("uiAmount") or 0.0)
                                            if idx not in mint_diffs: mint_diffs[idx] = {}
                                            mint_diffs[idx][mint] = amount
                                            
                                        for ptb in pre_token_balances:
                                            idx = ptb["accountIndex"]
                                            mint = ptb["mint"]
                                            amount = float(ptb.get("uiTokenAmount", {}).get("uiAmount") or 0.0)
                                            if idx not in mint_diffs: mint_diffs[idx] = {}
                                            mint_diffs[idx][mint] = mint_diffs[idx].get(mint, 0.0) - amount
                                            
                                        for idx, mints in mint_diffs.items():
                                            for mint, diff in mints.items():
                                                if diff < 0: # Negative means they sent it
                                                    amount_sent = abs(diff)
                                                    if amount_sent == 0: continue
                                                    
                                                    token_info = await get_token_info(chain_id, mint)
                                                    price_usd = token_info.get('price_usd', 0.0)
                                                    
                                                    if price_usd <= 0: continue
                                                    
                                                    usd_value = amount_sent * price_usd
                                                    if usd_value >= usd_threshold:
                                                        accounts = tx["transaction"]["message"]["accountKeys"]
                                                        sender_address = accounts[idx] if type(accounts[0]) == str else accounts[idx]["pubkey"]
                                                        await process_transaction(
                                                            db, chain_id, tx_hash, sender_address, "Unknown Receiver",
                                                            token_info.get('symbol', 'SPL'), mint, amount_sent, usd_value, block_time
                                                        )

                                finally:
                                    db.close()
                                    
                    last_slot = current_slot
                    
            except asyncio.CancelledError:
                logger.info("Stopping solana poller")
                break
            except Exception as e:
                pass
                
            await asyncio.sleep(5)


async def process_transaction(db, chain_id, tx_hash, from_addr, to_addr, symbol, token_addr, amount, usd_value, block_timestamp):
    """Helper to enrich wallets and save to DB."""
    existing = db.query(WhaleTransaction).filter_by(chain_id=chain_id, tx_hash=tx_hash, token_symbol=symbol).first()
    if existing:
        return

    from_wallet = await enrich_wallet(db, chain_id, from_addr)
    to_wallet = await enrich_wallet(db, chain_id, to_addr)
    
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
        token_symbol=symbol,
        token_address=token_addr,
        amount=amount,
        usd_value=usd_value,
        direction=direction,
        block_time=datetime.fromtimestamp(block_timestamp, tz=timezone.utc),
        raw_source="public_rpc"
    )
    db.add(whale_tx)
    try:
        db.commit()
        db.refresh(whale_tx)
    except Exception as e:
        db.rollback()
        # Usually IntegrityError due to unique constraint on (chain_id, tx_hash).
        # We can safely ignore duplicate transfers from the same transaction hash for now.
        return
    
    try:
        response = WhaleTransactionResponse.model_validate(whale_tx)
    except AttributeError:
        response = WhaleTransactionResponse.from_orm(whale_tx)
        
    import json
    await ws_manager.send_to_channel("whale", json.loads(response.json()))
    logger.info(f"[{chain_id.upper()} WHALE] {amount:,.2f} {symbol} ({usd_value:,.0f} USD)")

def start_whale_pollers(db_factory: Callable[[], Session]):
    """Start all chain pollers as asyncio background tasks."""
    global _polling_tasks
    
    try:
        db = next(db_factory())
        from app.models.whale import Chain
        for c_id, c_name in [("ethereum", "Ethereum"), ("bsc", "Binance Smart Chain"), ("solana", "Solana")]:
            if not db.query(Chain).filter_by(id=c_id).first():
                db.add(Chain(id=c_id, name=c_name))
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Failed to seed chains: {e}")

    if settings.ETH_RPC_URL:
        _polling_tasks.append(asyncio.create_task(poll_evm_chain("ethereum", settings.ETH_RPC_URL, db_factory)))
        
    if settings.BSC_RPC_URL:
        _polling_tasks.append(asyncio.create_task(poll_evm_chain("bsc", settings.BSC_RPC_URL, db_factory)))
        
    if settings.SOL_RPC_URL:
        _polling_tasks.append(asyncio.create_task(poll_solana_chain(settings.SOL_RPC_URL, db_factory)))

def stop_whale_pollers():
    """Cancel all polling tasks."""
    for task in _polling_tasks:
        task.cancel()
    _polling_tasks.clear()
