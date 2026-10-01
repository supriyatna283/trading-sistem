"""Data provider adapters for Whale Tracker."""
from .base import (
    BaseWhaleProvider,
    NetflowData,
    HolderBalance,
    HolderDistribution,
    WalletActivity,
    SmartWalletPosition,
    NewProjectInfo,
)
from .mock_provider import MockWhaleProvider

__all__ = [
    "BaseWhaleProvider",
    "NetflowData",
    "HolderBalance",
    "HolderDistribution",
    "WalletActivity",
    "SmartWalletPosition",
    "NewProjectInfo",
    "MockWhaleProvider",
]
