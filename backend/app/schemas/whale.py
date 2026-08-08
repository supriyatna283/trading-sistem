from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
from app.models.whale import WhaleDirection

# -- API Responses --
class WalletResponse(BaseModel):
    id: int
    chain_id: str
    address: str
    label: Optional[str] = None
    entity_type: str
    confidence: Optional[float] = None

    class Config:
        orm_mode = True

class WhaleTransactionResponse(BaseModel):
    id: int
    chain_id: str
    tx_hash: str
    from_wallet: Optional[WalletResponse] = None
    to_wallet: Optional[WalletResponse] = None
    token_symbol: str
    token_address: Optional[str] = None
    amount: float
    usd_value: float
    direction: WhaleDirection
    block_time: datetime
    detected_at: datetime
    raw_source: str

    class Config:
        orm_mode = True

# -- Webhook Payloads --

# Moralis ERC20 Transfer Schema
class MoralisErc20Transfer(BaseModel):
    transactionHash: str
    contract: str
    fromAddress: str
    toAddress: str
    valueWithDecimals: str
    tokenName: str
    tokenSymbol: str
    tokenDecimals: str

class MoralisWebhookPayload(BaseModel):
    confirmed: bool
    chainId: str
    streamId: str
    erc20Transfers: List[MoralisErc20Transfer]
    # Native transfers could also be added if monitoring ETH/BNB directly

# Helius Enriched Transaction Schema (Simplified for whales)
class HeliusTokenTransfer(BaseModel):
    fromUserAccount: str
    toUserAccount: str
    mint: str
    tokenAmount: float
    tokenStandard: str

class HeliusWebhookPayload(BaseModel):
    # Helius sends an array of enriched transactions
    __root__: List[Any] # Will parse manually in service due to complexity of structure
