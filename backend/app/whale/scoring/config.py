"""
Scoring Configuration
======================
Weights and thresholds for the whale scoring engine.
Loaded from `whale_scoring_config.json` in the project root.
Changes take effect on next scoring run — no restart required.

Default weights (must sum to approximately 1.0 for positive signals):
  accumulation:      0.35  (highest weight — stealth buy is most reliable)
  exchange_netflow:  0.25
  smart_wallet:      0.20
  concentration:    -0.15  (negative weight — concentration reduces score)
  new_project:       0.05  (small bonus, only for new tokens)
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Path to config file (relative to backend root or absolute)
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "whale_scoring_config.json"
)


@dataclass
class ScoringConfig:
    # Signal weights (positive = bullish contribution, negative = risk deduction)
    weight_accumulation: float = 0.35
    weight_netflow: float = 0.25
    weight_smart_wallet: float = 0.20
    weight_concentration: float = -0.15    # applied as abs, reduces score
    weight_new_project: float = 0.05

    # Lookback windows
    accumulation_days: int = 14
    netflow_days: int = 7
    smart_wallet_lookback_hours: int = 48

    # Concentration risk thresholds
    concentration_high_threshold_pct: float = 60.0   # top10 > this = HIGH risk
    concentration_very_high_pct: float = 75.0

    # Score → grade mapping
    grade_a_min: float = 80.0
    grade_b_min: float = 60.0
    grade_c_min: float = 40.0
    grade_d_min: float = 20.0

    # Alert thresholds
    alert_threshold: float = 70.0          # global: score >= this triggers alert
    alert_critical_threshold: float = 85.0 # score >= this triggers critical alert

    # Stale signal detection
    stale_price_move_pct: float = 8.0      # if price moved > X% since accumulation, flag as stale

    # Provider selection: "mock" | "hyperliquid" | "coingecko" | "auto"
    default_provider: str = "mock"

    # Extra flag: disable new project signal for all coins (if you don't track new tokens)
    enable_new_project_signal: bool = True

    # Grade labels
    grade_labels: dict = field(default_factory=lambda: {
        "A": "Sangat Bullish",
        "B": "Bullish",
        "C": "Netral",
        "D": "Waspada",
        "F": "Bearish / Risiko Tinggi",
    })


def load_scoring_config(path: str | None = None) -> ScoringConfig:
    """
    Load scoring config from JSON file. Falls back to defaults if file
    is missing or malformed. Hot-reloadable (no caching).
    """
    config_path = path or DEFAULT_CONFIG_PATH
    config = ScoringConfig()

    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data: dict = json.load(f)

            for key, val in data.items():
                if hasattr(config, key):
                    try:
                        setattr(config, key, type(getattr(config, key))(val))
                    except (TypeError, ValueError):
                        logger.warning(f"[ScoringConfig] Invalid value for {key}: {val}, using default")
            logger.debug(f"[ScoringConfig] Loaded from {config_path}")
        else:
            logger.info(f"[ScoringConfig] Config file not found at {config_path}, using defaults")
    except Exception as e:
        logger.warning(f"[ScoringConfig] Failed to load config: {e}, using defaults")

    return config


def save_scoring_config(config: ScoringConfig, path: str | None = None) -> None:
    """Persist current config to JSON file."""
    config_path = path or DEFAULT_CONFIG_PATH
    data = {
        "weight_accumulation": config.weight_accumulation,
        "weight_netflow": config.weight_netflow,
        "weight_smart_wallet": config.weight_smart_wallet,
        "weight_concentration": config.weight_concentration,
        "weight_new_project": config.weight_new_project,
        "accumulation_days": config.accumulation_days,
        "netflow_days": config.netflow_days,
        "smart_wallet_lookback_hours": config.smart_wallet_lookback_hours,
        "concentration_high_threshold_pct": config.concentration_high_threshold_pct,
        "concentration_very_high_pct": config.concentration_very_high_pct,
        "grade_a_min": config.grade_a_min,
        "grade_b_min": config.grade_b_min,
        "grade_c_min": config.grade_c_min,
        "grade_d_min": config.grade_d_min,
        "alert_threshold": config.alert_threshold,
        "alert_critical_threshold": config.alert_critical_threshold,
        "stale_price_move_pct": config.stale_price_move_pct,
        "default_provider": config.default_provider,
        "enable_new_project_signal": config.enable_new_project_signal,
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"[ScoringConfig] Saved to {config_path}")
