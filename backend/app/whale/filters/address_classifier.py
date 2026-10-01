"""
Address Classifier
====================
Determines the type of a blockchain address to prevent false positives.

Classification types:
  - exchange      : CEX hot/cold wallets (should not be counted as whale accumulation)
  - smart_money   : Wallets with proven profitable track records
  - whale         : Large holder with unknown identity
  - contract      : Smart contract address (LP pools, vaults, etc.)
  - burn          : Burn/dead addresses
  - unlabeled     : Unknown, not enough data
  - flagged       : Suspicious activity detected

Classification sources (in priority order):
  1. DB labels (manual labels + imported from Arkham/Nansen)
  2. Static known-address list (maintained in this file)
  3. Heuristic detection (contract bytecode check, balance patterns)
"""
from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AddressLabel(str, enum.Enum):
    EXCHANGE = "exchange"
    SMART_MONEY = "smart_money"
    WHALE = "whale"
    CONTRACT = "contract"
    BURN = "burn"
    UNLABELED = "unlabeled"
    FLAGGED = "flagged"


# ---------------------------------------------------------------------------
# Static address lists (extend as needed; or import via API)
# ---------------------------------------------------------------------------

KNOWN_EXCHANGES: dict[str, str] = {
    # Ethereum
    "0x28c6c06298d514db089934071355e22af164f014": "Binance 14",
    "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be": "Binance 1",
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance 8",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance 15",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance 16",
    "0x6ccc5ad199bf1c64b50f6e7dd530d71402402eb6": "Bybit",
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Bybit 2",
    "0x6f6c07d80d0d433ca787d552636e5d4379a5bded": "OKX 1",
    "0x98ec059dc3adfbdd63429454aeb0c990fba4a128": "OKX 2",
    "0x7830c87c02e56aff27fa8ab1241711331fa86f43": "Coinbase",
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase Prime",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase 2",
    "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740": "Coinbase 3",
    # Solana
    "5q544fkrfoe6tsebد7s8emxgtjyaktvhaw5q5pt4a82": "Binance Cold (SOL)",
    "hbgcroqvcngnxkybzsxabzlhzm2gwaxbzsf5gqkzjxt": "OKX (SOL)",
}

KNOWN_BURN_ADDRESSES: set[str] = {
    "0x000000000000000000000000000000000000dead",
    "0x0000000000000000000000000000000000000000",
    "1111111111111111111111111111111111111111111",   # Solana null
    "burnaddress1111111111111111111111111111111",
}

# Addresses that are known LP pools / protocol contracts (exclude from whale count)
KNOWN_CONTRACTS: set[str] = {
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",  # Uniswap v2 Router
    "0xe592427a0aece92de3edee1f18e0157c05861564",  # Uniswap v3 Router
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45",  # Uniswap v3 Router 2
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff",  # 0x Exchange Proxy
}


class AddressClassifier:
    """
    Classifies blockchain addresses to prevent false positives in whale detection.
    Consults DB first, then static lists, then heuristics.
    """

    def classify(
        self,
        address: str,
        chain_id: str,
        db: "Session | None" = None,
    ) -> tuple[AddressLabel, str | None]:
        """
        Returns (AddressLabel, label_name_or_None).
        Looks up DB → static exchange list → burn list → contract list → unlabeled.
        """
        addr_lower = address.lower()

        # 1. Check DB for manual labels
        if db is not None:
            try:
                from app.models.whale import Wallet
                wallet = db.query(Wallet).filter_by(address=address, chain_id=chain_id).first()
                if wallet and wallet.entity_type and wallet.entity_type != "unlabeled":
                    try:
                        label = AddressLabel(wallet.entity_type)
                    except ValueError:
                        label = AddressLabel.UNLABELED
                    return label, wallet.label
            except Exception:
                pass

        # 2. Static exchange list
        if addr_lower in KNOWN_EXCHANGES:
            return AddressLabel.EXCHANGE, KNOWN_EXCHANGES[addr_lower]

        # 3. Burn addresses
        if addr_lower in KNOWN_BURN_ADDRESSES:
            return AddressLabel.BURN, "Burn Address"

        # 4. Known contracts
        if addr_lower in KNOWN_CONTRACTS:
            return AddressLabel.CONTRACT, "Protocol Contract"

        # 5. Heuristic: EVM contracts start with 0x but are not EOAs
        # We can't check bytecode here without RPC, so return unlabeled
        return AddressLabel.UNLABELED, None

    def should_exclude_from_whale_score(
        self, label: AddressLabel
    ) -> bool:
        """True if address should be excluded from whale/accumulation counting."""
        return label in (
            AddressLabel.EXCHANGE,
            AddressLabel.BURN,
            AddressLabel.CONTRACT,
        )

    def import_labels_from_dict(
        self,
        label_dict: dict[str, dict],
        db: "Session",
        chain_id: str,
        source: str = "manual_import",
    ) -> int:
        """
        Bulk-import labels from a dict:
          { "0xAddress": {"label": "Binance Hot", "entity_type": "exchange"} }
        Returns count of imported labels.
        """
        from app.models.whale import Wallet
        from datetime import datetime, timezone
        count = 0
        for address, meta in label_dict.items():
            try:
                wallet = db.query(Wallet).filter_by(address=address, chain_id=chain_id).first()
                if not wallet:
                    wallet = Wallet(
                        chain_id=chain_id,
                        address=address,
                        entity_type=meta.get("entity_type", "unlabeled"),
                        label=meta.get("label"),
                        entity_source=source,
                        confidence=meta.get("confidence", 0.9),
                        last_enriched_at=datetime.now(timezone.utc),
                    )
                    db.add(wallet)
                else:
                    wallet.entity_type = meta.get("entity_type", wallet.entity_type)
                    wallet.label = meta.get("label", wallet.label)
                    wallet.entity_source = source
                    wallet.last_enriched_at = datetime.now(timezone.utc)
                count += 1
            except Exception as e:
                logger.warning(f"[AddressClassifier] Import failed for {address}: {e}")
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[AddressClassifier] Commit failed: {e}")
        return count
