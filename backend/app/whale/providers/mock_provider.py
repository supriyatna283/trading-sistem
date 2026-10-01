"""
Mock Provider
=============
Deterministic mock data for testing the full pipeline without any API keys.
Values are derived from a hash of (symbol, date) so they are stable across
runs but vary per asset — good for unit tests and UI development.
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone
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


def _seed(text: str) -> int:
    """Stable integer seed from a string."""
    return int(hashlib.md5(text.encode()).hexdigest(), 16)


def _float(seed: int, lo: float, hi: float) -> float:
    return lo + (seed % 100_000) / 100_000 * (hi - lo)


# Pre-defined mock smart wallets (used across activity + positions)
MOCK_SMART_WALLETS = [
    "0xSmartMoney_Alpha_001",
    "0xSmartMoney_Beta_002",
    "0xSmartMoney_Gamma_003",
    "So1SmartSolana_Delta_004",
    "HL_SmartPerp_Epsilon_005",
]

# Mock exchange addresses — will be labelled "exchange" and excluded from concentration
MOCK_EXCHANGE_ADDRESSES = {
    "0xExchange_Binance_Hot_Wallet",
    "0xExchange_Coinbase_Custody",
    "0xExchange_OKX_Wallet",
    "0xBurn_DeadBeef_000000",
}


class MockWhaleProvider(BaseWhaleProvider):
    """
    Fully offline mock provider. All values are deterministic.
    Useful for unit testing and frontend development without API keys.
    """

    @property
    def name(self) -> str:
        return "mock"

    # ------------------------------------------------------------------
    # Exchange Netflow
    # ------------------------------------------------------------------

    async def get_exchange_netflow(
        self, symbol: str, chain_id: str, days: int = 7
    ) -> Optional[NetflowData]:
        base = _seed(f"netflow:{symbol}:{days}")
        total_flow = _float(base, 50_000_000, 500_000_000)

        # Positive net = more outflow (bullish mock for BTC/HYPE)
        inflow_pct = _float(base >> 4, 0.35, 0.65)
        inflow = total_flow * inflow_pct
        outflow = total_flow * (1 - inflow_pct)
        net = outflow - inflow

        snapshots = []
        for i in range(days):
            day_seed = _seed(f"netflow_daily:{symbol}:{i}")
            day_date = (datetime.utcnow() - timedelta(days=days - i)).strftime("%Y-%m-%d")
            d_in = _float(day_seed, 2_000_000, 30_000_000)
            d_out = _float(day_seed >> 3, 2_000_000, 35_000_000)
            snapshots.append({
                "date": day_date,
                "inflow": round(d_in, 0),
                "outflow": round(d_out, 0),
                "net": round(d_out - d_in, 0),
            })

        return NetflowData(
            symbol=symbol,
            chain_id=chain_id,
            period_days=days,
            inflow_usd=round(inflow, 0),
            outflow_usd=round(outflow, 0),
            net_flow_usd=round(net, 0),
            daily_snapshots=snapshots,
            source=self.name,
        )

    # ------------------------------------------------------------------
    # Holder Balances
    # ------------------------------------------------------------------

    async def get_top_holder_balances(
        self, symbol: str, chain_id: str, top_n: int = 50
    ) -> list[HolderBalance]:
        holders: list[HolderBalance] = []
        total_supply_mock = 21_000_000 if symbol == "BTC" else 1_000_000_000

        # Add exchange addresses first (will be excluded from concentration)
        for i, addr in enumerate(list(MOCK_EXCHANGE_ADDRESSES)[:3]):
            seed = _seed(f"exchange:{symbol}:{i}")
            balance = _float(seed, total_supply_mock * 0.04, total_supply_mock * 0.10)
            holders.append(HolderBalance(
                address=addr,
                balance=balance,
                balance_usd=balance * _float(seed, 50, 65000),
                entity_type="exchange",
                label=f"Mock Exchange {i + 1}",
                is_excluded=True,
                chain_id=chain_id,
            ))

        # Add smart wallets
        for i, addr in enumerate(MOCK_SMART_WALLETS[:3]):
            seed = _seed(f"smart:{symbol}:{addr}")
            balance = _float(seed, total_supply_mock * 0.005, total_supply_mock * 0.02)
            holders.append(HolderBalance(
                address=addr,
                balance=balance,
                balance_usd=balance * _float(seed >> 1, 50, 65000),
                entity_type="smart_money",
                label=f"Smart Money #{i + 1}",
                is_excluded=False,
                chain_id=chain_id,
            ))

        # Add generic whales
        remaining = top_n - len(holders)
        for i in range(remaining):
            seed = _seed(f"whale:{symbol}:{i}")
            balance = _float(seed, total_supply_mock * 0.001, total_supply_mock * 0.015) / (
                math.log(i + 2)
            )
            holders.append(HolderBalance(
                address=f"0xWhaleAddress_{symbol}_{i:03d}",
                balance=balance,
                balance_usd=balance * _float(seed >> 2, 50, 65000),
                entity_type="whale",
                label=None,
                is_excluded=False,
                chain_id=chain_id,
            ))

        return holders

    async def get_holder_distribution(
        self, symbol: str, chain_id: str
    ) -> Optional[HolderDistribution]:
        seed = _seed(f"dist:{symbol}")
        total_supply = 21_000_000 if symbol == "BTC" else 1_000_000_000
        top10 = _float(seed, 15.0, 75.0)
        top20 = top10 + _float(seed >> 1, 5.0, 15.0)
        top50 = top20 + _float(seed >> 2, 5.0, 10.0)

        holders = await self.get_top_holder_balances(symbol, chain_id, top_n=50)

        return HolderDistribution(
            symbol=symbol,
            chain_id=chain_id,
            total_supply=total_supply,
            circulating_supply=total_supply * 0.85,
            top10_pct=round(top10, 2),
            top20_pct=round(min(top20, 90.0), 2),
            top50_pct=round(min(top50, 95.0), 2),
            holders=holders,
            is_high_concentration=top10 > 60.0,
            source=self.name,
        )

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
        price_mock = _float(_seed(f"price:{symbol}"), 0.01, 65000)

        for addr in wallet_addresses:
            seed = _seed(f"activity:{addr}:{symbol}")
            # ~60% chance of any activity in the lookback window
            if seed % 10 < 4:
                continue

            action_idx = seed % 4
            actions = ["accumulate", "open_long", "open_short", "close"]
            action = actions[action_idx]

            amount = _float(seed >> 2, 100, 50_000)
            amount_usd = amount * price_mock
            hours_ago = _float(seed >> 4, 0.5, lookback_hours)
            ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)

            activities.append(WalletActivity(
                wallet_address=addr,
                symbol=symbol,
                chain_id=chain_id,
                action=action,
                amount=round(amount, 4),
                amount_usd=round(amount_usd, 2),
                price_at_action=price_mock,
                timestamp=ts,
                pnl_usd=_float(seed >> 6, -5000, 50000) if action == "close" else None,
                win_rate=_float(seed >> 8, 55.0, 85.0),
                label=f"Smart Money #{wallet_addresses.index(addr) + 1}",
                source=self.name,
            ))

        return activities

    async def get_smart_wallet_positions(
        self, wallet_addresses: list[str], symbol: str, chain_id: str
    ) -> list[SmartWalletPosition]:
        positions: list[SmartWalletPosition] = []
        price_mock = _float(_seed(f"price:{symbol}"), 0.01, 65000)

        for addr in wallet_addresses:
            seed = _seed(f"pos:{addr}:{symbol}")
            # ~50% chance of having an open position
            if seed % 2 == 0:
                continue

            side = "long" if seed % 3 != 0 else "short"
            size = _float(seed >> 2, 100, 10_000)
            entry = price_mock * _float(seed >> 4, 0.90, 1.10)
            unrealised = (price_mock - entry) * size * (1 if side == "long" else -1)

            positions.append(SmartWalletPosition(
                wallet_address=addr,
                symbol=symbol,
                chain_id=chain_id,
                side=side,
                size=round(size, 4),
                size_usd=round(size * price_mock, 2),
                entry_price=round(entry, 4),
                unrealised_pnl=round(unrealised, 2),
                leverage=_float(seed >> 6, 1.0, 10.0),
                opened_at=datetime.now(timezone.utc) - timedelta(hours=_float(seed >> 8, 1, 168)),
                label=f"Smart Money #{wallet_addresses.index(addr) + 1}",
                source=self.name,
            ))

        return positions

    # ------------------------------------------------------------------
    # New Project Info
    # ------------------------------------------------------------------

    async def get_new_project_info(
        self, symbol: str, chain_id: str, token_address: str
    ) -> Optional[NewProjectInfo]:
        # Mature assets don't need new-project scoring
        if symbol in ("BTC", "ETH", "SOL", "BNB", "HYPE"):
            return None

        seed = _seed(f"newproject:{symbol}:{token_address}")
        deploy_days_ago = _float(seed, 1, 180)
        locked = bool(seed % 3)
        flags: list[str] = []

        if not locked:
            flags.append("liquidity_not_locked")
        top_holder_age = _float(seed >> 4, 0.5, 365)
        if top_holder_age < 7:
            flags.append("new_whale_wallets_suspicious")
        concentration_pct = _float(seed >> 8, 20, 95)
        if concentration_pct > 70:
            flags.append("high_concentration_risk")

        return NewProjectInfo(
            symbol=symbol,
            chain_id=chain_id,
            token_address=token_address,
            deploy_timestamp=datetime.now(timezone.utc) - timedelta(days=deploy_days_ago),
            liquidity_locked=locked,
            lock_duration_days=int(_float(seed >> 2, 30, 365)) if locked else None,
            vesting_exists=bool(seed % 2),
            top_holder_wallet_age_days=round(top_holder_age, 1),
            early_entry_wallets=int(_float(seed >> 6, 0, 10)),
            risk_flags=flags,
            source=self.name,
        )

    # ------------------------------------------------------------------
    # Accumulation Series
    # ------------------------------------------------------------------

    async def get_accumulation_series(
        self, symbol: str, chain_id: str, top_n_wallets: int = 20, days: int = 14
    ) -> list[dict]:
        series = []
        for i in range(days):
            day_seed = _seed(f"accum:{symbol}:{i}")
            date_str = (datetime.utcnow() - timedelta(days=days - i - 1)).strftime("%Y-%m-%d")
            # Positive = net accumulation, negative = net distribution
            net_change = _float(day_seed, -500_000, 1_500_000)
            active = int(_float(day_seed >> 2, 0, top_n_wallets))
            series.append({
                "date": date_str,
                "net_balance_change": round(net_change, 0),
                "active_accumulators": active,
                "is_accumulation": net_change > 0,
            })
        return series
