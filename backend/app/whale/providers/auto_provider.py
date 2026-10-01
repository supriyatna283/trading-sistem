"""
Auto Whale Provider
===================
A composite provider that dynamically routes requests to the appropriate 
real-data provider based on the chain_id or symbol.

Routing Logic:
  - chain_id == "hyperliquid" -> HyperliquidProvider
  - fallback -> CoinGeckoProvider (for metadata and distribution)
"""
from __future__ import annotations

import logging
from typing import Optional

from .base import (
    BaseWhaleProvider,
    NetflowData,
    HolderBalance,
    HolderDistribution,
    WalletActivity,
    SmartWalletPosition,
    NewProjectInfo,
)
from .hyperliquid_provider import HyperliquidProvider
from .coingecko_provider import CoinGeckoProvider

logger = logging.getLogger(__name__)


class AutoWhaleProvider(BaseWhaleProvider):
    """Dynamically routes to real data providers."""

    def __init__(self):
        self.hl_provider = HyperliquidProvider()
        self.cg_provider = CoinGeckoProvider()

    @property
    def name(self) -> str:
        return "auto"

    def _get_provider(self, chain_id: str) -> BaseWhaleProvider:
        if chain_id.lower() == "hyperliquid":
            return self.hl_provider
        # For non-HL chains, Etherscan/Solscan would go here. 
        # Since they are not fully implemented yet, we fallback to CoinGecko
        # which provides basic metadata and supply info for all chains.
        return self.cg_provider

    async def get_exchange_netflow(
        self, symbol: str, chain_id: str, days: int = 7
    ) -> Optional[NetflowData]:
        provider = self._get_provider(chain_id)
        return await provider.get_exchange_netflow(symbol, chain_id, days)

    async def get_top_holder_balances(
        self, symbol: str, chain_id: str, top_n: int = 50
    ) -> list[HolderBalance]:
        provider = self._get_provider(chain_id)
        return await provider.get_top_holder_balances(symbol, chain_id, top_n)

    async def get_holder_distribution(
        self, symbol: str, chain_id: str
    ) -> Optional[HolderDistribution]:
        provider = self._get_provider(chain_id)
        return await provider.get_holder_distribution(symbol, chain_id)

    async def get_smart_wallet_activity(
        self, wallet_addresses: list[str], symbol: str, chain_id: str, lookback_hours: int = 48
    ) -> list[WalletActivity]:
        provider = self._get_provider(chain_id)
        return await provider.get_smart_wallet_activity(wallet_addresses, symbol, chain_id, lookback_hours)

    async def get_smart_wallet_positions(
        self, wallet_addresses: list[str], symbol: str, chain_id: str
    ) -> list[SmartWalletPosition]:
        provider = self._get_provider(chain_id)
        return await provider.get_smart_wallet_positions(wallet_addresses, symbol, chain_id)

    async def get_new_project_info(
        self, symbol: str, chain_id: str, token_address: str
    ) -> Optional[NewProjectInfo]:
        provider = self._get_provider(chain_id)
        return await provider.get_new_project_info(symbol, chain_id, token_address)

    async def get_accumulation_series(
        self, symbol: str, chain_id: str, top_n_wallets: int = 20, days: int = 14
    ) -> list[dict]:
        provider = self._get_provider(chain_id)
        return await provider.get_accumulation_series(symbol, chain_id, top_n_wallets, days)
