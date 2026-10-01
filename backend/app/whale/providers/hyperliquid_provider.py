"""
Hyperliquid Provider
=====================
Fetches real data from Hyperliquid's public API (no API key required).

Endpoints used:
  - POST https://api.hyperliquid.xyz/info  (meta, open orders, user state)
  - WebSocket wss://api.hyperliquid.xyz/ws (live trades — handled by existing whale_detector)

This provider covers:
  - Open positions per address (smart wallet positions)
  - Trade history per address (smart wallet activity)
  - Aggregate funding/volume as a proxy for exchange netflow

Docs: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
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

HL_API = "https://api.hyperliquid.xyz/info"
HL_TIMEOUT = 10.0


class HyperliquidProvider(BaseWhaleProvider):
    """
    Adapter for Hyperliquid public REST API.
    Only covers perpetual markets (HYPE, BTC-perp, ETH-perp, etc.).
    Spot holder distribution is NOT available from HL — falls back to None.
    """

    @property
    def name(self) -> str:
        return "hyperliquid"

    async def _post(self, payload: dict) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=HL_TIMEOUT) as client:
                resp = await client.post(HL_API, json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"[HyperliquidProvider] API error: {e}")
            return None

    # ------------------------------------------------------------------
    # Exchange Netflow — approximated via open interest delta
    # ------------------------------------------------------------------

    async def get_exchange_netflow(
        self, symbol: str, chain_id: str, days: int = 7
    ) -> Optional[NetflowData]:
        """
        Hyperliquid is a perp DEX, not a CEX. We approximate 'flow' as:
          - OI increase = long bias = "outflow equivalent" (bullish)
          - OI decrease = short bias = "inflow equivalent" (bearish)
        """
        data = await self._post({"type": "metaAndAssetCtxs"})
        if not data or len(data) < 2:
            return None

        universe = data[0].get("universe", [])
        asset_ctxs = data[1]

        # Find target symbol
        target_ctx = None
        for i, asset in enumerate(universe):
            if asset.get("name", "").upper() == symbol.upper():
                if i < len(asset_ctxs):
                    target_ctx = asset_ctxs[i]
                break

        if not target_ctx:
            return None

        oi = float(target_ctx.get("openInterest", 0))
        mark_px = float(target_ctx.get("markPx", 0))
        oi_usd = oi * mark_px

        # Simplified: use OI as proxy for outflow, day volume as inflow
        day_volume = float(target_ctx.get("dayNtlVlm", 0))

        return NetflowData(
            symbol=symbol,
            chain_id="hyperliquid",
            period_days=days,
            inflow_usd=day_volume * 0.4,          # rough proxy
            outflow_usd=oi_usd,
            net_flow_usd=oi_usd - day_volume * 0.4,
            daily_snapshots=[],                    # historical not available via free API
            source=self.name,
        )

    # ------------------------------------------------------------------
    # Holder Balances — not applicable for perp DEX
    # ------------------------------------------------------------------

    async def get_top_holder_balances(
        self, symbol: str, chain_id: str, top_n: int = 50
    ) -> list[HolderBalance]:
        # HL is a perp DEX, no token holder list available
        return []

    async def get_holder_distribution(
        self, symbol: str, chain_id: str
    ) -> Optional[HolderDistribution]:
        return None

    # ------------------------------------------------------------------
    # Smart Wallet Activity
    # ------------------------------------------------------------------

    async def get_smart_wallet_activity(
        self,
        wallet_addresses: list[str],
        symbol: str,
        chain_id: str,
        lookback_hours: int = 48,
    ) -> list[WalletActivity]:
        activities: list[WalletActivity] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        for addr in wallet_addresses:
            data = await self._post({
                "type": "userFills",
                "user": addr,
            })
            if not data:
                continue

            for fill in data:
                try:
                    coin = fill.get("coin", "")
                    if coin.upper() != symbol.upper():
                        continue
                    ts = datetime.fromtimestamp(
                        fill.get("time", 0) / 1000, tz=timezone.utc
                    )
                    if ts < cutoff:
                        continue

                    side = fill.get("side", "B")  # B=buy/long, A=sell/short
                    action = "accumulate" if side == "B" else "distribute"
                    px = float(fill.get("px", 0))
                    sz = float(fill.get("sz", 0))

                    activities.append(WalletActivity(
                        wallet_address=addr,
                        symbol=symbol,
                        chain_id="hyperliquid",
                        action=action,
                        amount=sz,
                        amount_usd=sz * px,
                        price_at_action=px,
                        timestamp=ts,
                        source=self.name,
                    ))
                except Exception:
                    continue

        return activities

    async def get_smart_wallet_positions(
        self, wallet_addresses: list[str], symbol: str, chain_id: str
    ) -> list[SmartWalletPosition]:
        positions: list[SmartWalletPosition] = []

        for addr in wallet_addresses:
            data = await self._post({
                "type": "clearinghouseState",
                "user": addr,
            })
            if not data:
                continue

            asset_positions = data.get("assetPositions", [])
            for pos_wrapper in asset_positions:
                pos = pos_wrapper.get("position", {})
                if pos.get("coin", "").upper() != symbol.upper():
                    continue
                try:
                    szi = float(pos.get("szi", 0))
                    entry_px = float(pos.get("entryPx", 0))
                    unrealised = float(pos.get("unrealizedPnl", 0))
                    mark_px = float(data.get("marginSummary", {}).get("accountValue", entry_px))

                    positions.append(SmartWalletPosition(
                        wallet_address=addr,
                        symbol=symbol,
                        chain_id="hyperliquid",
                        side="long" if szi > 0 else "short",
                        size=abs(szi),
                        size_usd=abs(szi) * entry_px,
                        entry_price=entry_px,
                        unrealised_pnl=unrealised,
                        leverage=pos.get("leverage", {}).get("value"),
                        source=self.name,
                    ))
                except Exception:
                    continue

        return positions

    # ------------------------------------------------------------------
    # New Project / Accumulation — not applicable for HL perps
    # ------------------------------------------------------------------

    async def get_new_project_info(
        self, symbol: str, chain_id: str, token_address: str
    ) -> Optional[NewProjectInfo]:
        return None

    async def get_accumulation_series(
        self, symbol: str, chain_id: str, top_n_wallets: int = 20, days: int = 14
    ) -> list[dict]:
        # Would require querying each wallet's historical fills — expensive.
        # Defer to the scoring engine using existing whale_transactions table data.
        return []
