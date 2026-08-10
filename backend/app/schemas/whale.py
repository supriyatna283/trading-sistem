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
    win_rate: Optional[float] = None
    pnl_usd: Optional[float] = None

    class Config:
        from_attributes = True

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
        from_attributes = True


