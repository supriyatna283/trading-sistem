"""
CoinGecko Provider (Free Tier)
================================
Uses CoinGecko public API (no API key required for most endpoints).
Rate limit: ~10-30 req/min on free tier.

Covers:
  - Holder distribution (approximated from on-chain data)
  - Market cap, circulating supply
  - Token metadata

Does NOT cover:
  - Detailed individual wallet balances (need Etherscan/Solscan for that)
  - Smart wallet activity (need chain-specific provider)
  - Exchange netflow (need CryptoQuant or Glassnode for that)

CoinGecko ID mapping: We use the CoinGecko id (e.g., 'bitcoin', 'ethereum').
The watchlist_coins table should store this id in a 'coingecko_id' field.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from .base import (
    BaseWhaleProvider,
    NetflowData,
    HolderBalance,
    HolderDistribution,
    WalletActivity,
    SmartWalletPosition,
    NewProjectInfo,
)

logger = logging.getLogger(__name__)

CG_BASE = "https://api.coingecko.com/api/v3"
CG_TIMEOUT = 15.0

# Known CoinGecko IDs for common symbols
SYMBOL_TO_CG_ID: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "HYPE": "hyperliquid",
    "WIF": "dogwifcoin",
    "BONK": "bonk",
}


class CoinGeckoProvider(BaseWhaleProvider):
    """
    CoinGecko free-tier adapter.
    Primary use: holder distribution & supply data.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key  # CoinGecko Pro key (optional)

    @property
    def name(self) -> str:
        return "coingecko"

    def _cg_id(self, symbol: str) -> str:
        return SYMBOL_TO_CG_ID.get(symbol.upper(), symbol.lower())

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> Optional[dict | list]:
        headers = {}
        if self._api_key:
            headers["x-cg-pro-api-key"] = self._api_key
        try:
            async with httpx.AsyncClient(timeout=CG_TIMEOUT) as client:
                resp = await client.get(f"{CG_BASE}{endpoint}", params=params, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"[CoinGeckoProvider] {endpoint}: {e}")
            return None

    # ------------------------------------------------------------------
    # Exchange Netflow — CoinGecko doesn't provide this; return None
    # ------------------------------------------------------------------

    async def get_exchange_netflow(
        self, symbol: str, chain_id: str, days: int = 7
    ) -> Optional[NetflowData]:
        return None  # Use CryptoQuant or Glassnode adapter for this

    # ------------------------------------------------------------------
    # Holder Distribution via coin/id/tickers (approximated)
    # ------------------------------------------------------------------

    async def get_top_holder_balances(
        self, symbol: str, chain_id: str, top_n: int = 50
    ) -> list[HolderBalance]:
        # CoinGecko free tier doesn't expose wallet-level data.
        # Return empty; use Etherscan/Solscan providers for this.
        return []

    async def get_holder_distribution(
        self, symbol: str, chain_id: str
    ) -> Optional[HolderDistribution]:
        cg_id = self._cg_id(symbol)
        data = await self._get(f"/coins/{cg_id}", params={
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "false",
            "developer_data": "false",
        })
        if not data or not isinstance(data, dict):
            return None

        market_data = data.get("market_data", {})
        total_supply = float(market_data.get("total_supply") or 0)
        circulating = float(market_data.get("circulating_supply") or total_supply)

        # CoinGecko doesn't give top-holder %, so we return a shell object.
        # The actual concentration data comes from Etherscan/Solscan providers.
        return HolderDistribution(
            symbol=symbol,
            chain_id=chain_id,
            total_supply=total_supply,
            circulating_supply=circulating,
            top10_pct=0.0,   # fill from chain-specific provider
            top20_pct=0.0,
            top50_pct=0.0,
            holders=[],
            is_high_concentration=False,
            source=self.name,
        )

    # ------------------------------------------------------------------
    # Smart Wallet — not applicable
    # ------------------------------------------------------------------

    async def get_smart_wallet_activity(
        self, wallet_addresses: list[str], symbol: str, chain_id: str, lookback_hours: int = 48
    ) -> list[WalletActivity]:
        return []

    async def get_smart_wallet_positions(
        self, wallet_addresses: list[str], symbol: str, chain_id: str
    ) -> list[SmartWalletPosition]:
        return []

    # ------------------------------------------------------------------
    # New Project Info
    # ------------------------------------------------------------------

    async def get_new_project_info(
        self, symbol: str, chain_id: str, token_address: str
    ) -> Optional[NewProjectInfo]:
        cg_id = self._cg_id(symbol)
        data = await self._get(f"/coins/{cg_id}", params={
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "false",
            "developer_data": "false",
        })
        if not data or not isinstance(data, dict):
            return None

        genesis_date_str = data.get("genesis_date")
        deploy_ts = None
        if genesis_date_str:
            try:
                deploy_ts = datetime.fromisoformat(genesis_date_str).replace(tzinfo=timezone.utc)
            except Exception:
                pass

        flags: list[str] = []
        # CoinGecko doesn't expose lock status, so flag as unknown
        flags.append("lock_status_unknown")

        return NewProjectInfo(
            symbol=symbol,
            chain_id=chain_id,
            token_address=token_address,
            deploy_timestamp=deploy_ts,
            liquidity_locked=None,  # unknown from CoinGecko
            risk_flags=flags,
            source=self.name,
        )

    async def get_accumulation_series(
        self, symbol: str, chain_id: str, top_n_wallets: int = 20, days: int = 14
    ) -> list[dict]:
        return []
