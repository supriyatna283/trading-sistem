"""Signal detectors for Whale Tracker."""
from .accumulation import AccumulationSignal
from .exchange_netflow import ExchangeNetflowSignal
from .smart_wallet import SmartWalletSignal
from .holder_concentration import HolderConcentrationSignal
from .new_project import NewProjectSignal

__all__ = [
    "AccumulationSignal",
    "ExchangeNetflowSignal",
    "SmartWalletSignal",
    "HolderConcentrationSignal",
    "NewProjectSignal",
]
