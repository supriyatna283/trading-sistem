"""
Abstract Base Provider
=======================
All data providers (Hyperliquid, Etherscan, Solscan, CoinGecko, mock)
must implement this interface. The scoring engine only depends on this
contract — swapping providers requires zero changes to scoring logic.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# ---------------------------------------------------------------------------
# Data Transfer Objects (provider-agnostic, normalised schema)
# ---------------------------------------------------------------------------

@dataclass
class NetflowData:
    """Exchange net flow for a given symbol over a time window."""
    symbol: str
    chain_id: str
    period_days: int
    inflow_usd: float          # USD entering exchanges (bearish pressure)
    outflow_usd: float         # USD leaving exchanges (bullish pressure)
    net_flow_usd: float        # outflow - inflow (positive = bullish)
    daily_snapshots: list[dict] = field(default_factory=list)
    # e.g. [{"date": "2026-09-28", "inflow": 5e6, "outflow": 8e6, "net": 3e6}]
    source: str = "unknown"
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HolderBalance:
    """A single large holder's balance snapshot."""
    address: str
    balance: float             # token amount
    balance_usd: float
    entity_type: str           # "exchange", "whale", "smart_money", "contract", "burn", "unknown"
    label: Optional[str] = None
    is_excluded: bool = False  # True if this address should be excluded from concentration calc
    chain_id: str = "unknown"
    snapshot_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HolderDistribution:
    """Supply distribution across top N holders."""
    symbol: str
    chain_id: str
    total_supply: float
    circulating_supply: float
    top10_pct: float           # % held by top 10 (excl. exchanges/burn/contracts)
    top20_pct: float
    top50_pct: float
    holders: list[HolderBalance] = field(default_factory=list)
    # Concentration risk: True if top10 > threshold in scoring config
    is_high_concentration: bool = False
    source: str = "unknown"
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WalletActivity:
    """Activity record of a tracked smart wallet for a given symbol."""
    wallet_address: str
    symbol: str
    chain_id: str
    action: str                # "open_long", "open_short", "close", "accumulate", "distribute"
    amount: float
    amount_usd: float
    price_at_action: float
    timestamp: datetime
    pnl_usd: Optional[float] = None      # realised PnL if closing
    win_rate: Optional[float] = None     # historical win rate of this wallet
    label: Optional[str] = None
    source: str = "unknown"


@dataclass
class SmartWalletPosition:
    """Open position of a smart wallet on a perp or spot market."""
    wallet_address: str
    symbol: str
    chain_id: str
    side: str                  # "long" / "short"
    size: float
    size_usd: float
    entry_price: float
    unrealised_pnl: float
    leverage: Optional[float] = None
    opened_at: Optional[datetime] = None
    label: Optional[str] = None
    source: str = "unknown"


@dataclass
class NewProjectInfo:
    """Metadata for new project risk assessment."""
    symbol: str
    chain_id: str
    token_address: str
    deploy_timestamp: Optional[datetime] = None   # when token was deployed
    liquidity_locked: Optional[bool] = None        # True if LP locked
    lock_duration_days: Optional[int] = None
    vesting_exists: Optional[bool] = None
    top_holder_wallet_age_days: Optional[float] = None  # avg age of top whales
    early_entry_wallets: int = 0   # wallets that entered pre-launch/early
    risk_flags: list[str] = field(default_factory=list)
    source: str = "unknown"


# ---------------------------------------------------------------------------
# Abstract Provider
# ---------------------------------------------------------------------------

class BaseWhaleProvider(ABC):
    """
    All concrete providers must implement every method.
    Raise `NotImplementedError` only for methods your provider genuinely
    cannot support — the scoring engine handles `None` gracefully.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name, e.g. 'hyperliquid', 'mock'."""

    # -- Exchange Netflow ---------------------------------------------------

    @abstractmethod
    async def get_exchange_netflow(
        self, symbol: str, chain_id: str, days: int = 7
    ) -> Optional[NetflowData]:
        """
        Return net USD flow to/from centralised exchanges for `symbol`
        over the last `days` days. Return None if data unavailable.
        """

    # -- Holder Balances ---------------------------------------------------

    @abstractmethod
    async def get_top_holder_balances(
        self, symbol: str, chain_id: str, top_n: int = 50
    ) -> list[HolderBalance]:
        """
        Return the top N holder addresses with their balances.
        Must NOT include known exchanges, burn addresses, or contracts
        in the whale/smart-money category — label them properly.
        """

    @abstractmethod
    async def get_holder_distribution(
        self, symbol: str, chain_id: str
    ) -> Optional[HolderDistribution]:
        """Return supply distribution across top 10/20/50 holders."""

    # -- Smart Wallet Activity ---------------------------------------------

    @abstractmethod
    async def get_smart_wallet_activity(
        self,
        wallet_addresses: list[str],
        symbol: str,
        chain_id: str,
        lookback_hours: int = 48,
    ) -> list[WalletActivity]:
        """
        Return recent activity (buys/sells/accumulations) of the given
        smart wallet addresses for `symbol`.
        """

    @abstractmethod
    async def get_smart_wallet_positions(
        self, wallet_addresses: list[str], symbol: str, chain_id: str
    ) -> list[SmartWalletPosition]:
        """Return currently open positions of smart wallets for `symbol`."""

    # -- New Project Info --------------------------------------------------

    @abstractmethod
    async def get_new_project_info(
        self, symbol: str, chain_id: str, token_address: str
    ) -> Optional[NewProjectInfo]:
        """
        Return risk metadata for a new project: lock status, deploy age,
        early entry wallets, etc. Return None for mature assets like BTC.
        """

    # -- Accumulation History (pulled from on-chain tx / snapshots) --------

    @abstractmethod
    async def get_accumulation_series(
        self, symbol: str, chain_id: str, top_n_wallets: int = 20, days: int = 14
    ) -> list[dict]:
        """
        Return daily aggregate net balance change for top N non-exchange wallets.
        Shape: [{"date": "2026-09-28", "net_balance_change": 1200.5, "active_accumulators": 3}]
        """
