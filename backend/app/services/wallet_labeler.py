import logging
from sqlalchemy.orm import Session
from app.models.whale import Wallet
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

KNOWN_HOT_WALLETS = {
    # Binance hot wallets (Mocked/Simplified for demo)
    "0x28C6c06298d514Db089934071355E22Af164F014": "Binance 14",
    "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE": "Binance 1",
    "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3": "Binance 8",
    # Solana Binance
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pT4A82": "Binance Cold",
    # OKX hot wallets
    "0x6F6c07d80D0D433ca787d552636E5D4379a5BdeD": "OKX",
}

async def enrich_wallet(db: Session, chain_id: str, address: str) -> Wallet:
    """Get or create wallet, assign basic labels statically since Arkham is removed."""
    wallet = db.query(Wallet).filter(
        Wallet.chain_id == chain_id,
        Wallet.address == address
    ).first()

    now = datetime.now(timezone.utc)

    if not wallet:
        wallet = Wallet(
            chain_id=chain_id,
            address=address,
            entity_type="unlabeled"
        )
        db.add(wallet)
        db.commit()
        db.refresh(wallet)

    needs_enrichment = False
    if not wallet.last_enriched_at:
        needs_enrichment = True
    else:
        time_diff = now - wallet.last_enriched_at.replace(tzinfo=timezone.utc)
        if time_diff.total_seconds() > 86400 * 7: # Weekly refresh is fine for static list
            needs_enrichment = True

    if needs_enrichment:
        # Very simple static labeling
        if address in KNOWN_HOT_WALLETS:
            wallet.entity_type = "exchange"
            wallet.label = KNOWN_HOT_WALLETS[address]
            wallet.entity_source = "static_list"
            wallet.confidence = 1.0
        else:
            wallet.entity_type = "unlabeled"
            wallet.label = None
            wallet.entity_source = "static_list"
            wallet.confidence = 0.5
            
        wallet.last_enriched_at = now
        db.commit()
        db.refresh(wallet)

    return wallet
