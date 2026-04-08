"""Configuration loader for the CITS trading system.

Loads ``cits/config.yml``, merges with environment variable overrides,
and returns a flat dict compatible with :data:`TradingGraph.DEFAULT_CONFIG`.

Environment variable overrides (all optional):
    ``CITS_LLM_PROVIDER``
    ``CITS_DEEP_THINK_LLM``
    ``CITS_QUICK_THINK_LLM``
    ``CITS_TRADING_MODE``          – ``paper`` or ``live``
    ``CITS_MAX_DEBATE_ROUNDS``
    ``CITS_LOG_DIR``
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Resolve the config file relative to this module's directory
_CONFIG_DIR = Path(__file__).resolve().parent
_DEFAULT_CONFIG_PATH = _CONFIG_DIR / "config.yml"

# Fallback values when config.yml is missing
_FALLBACK_CONFIG: dict[str, Any] = {
    "llm_provider": "anthropic",
    "deep_think_llm": "claude-opus-4-6",
    "quick_think_llm": "claude-sonnet-4-20250514",
    "max_debate_rounds": 2,
    "paper_mode": True,
    "log_dir": "cits/logs",
    "analyst_temperature": 0.3,
    "debate_temperature": 0.4,
    "trader_temperature": 0.2,
}


def _flatten_yaml(raw: dict[str, Any]) -> dict[str, Any]:
    """Flatten the nested YAML structure into the flat dict TradingGraph expects."""
    llm = raw.get("llm", {})
    trading = raw.get("trading", {})
    risk = raw.get("risk", {})
    broker = raw.get("broker", {})
    log_cfg = raw.get("logging", {})

    flat: dict[str, Any] = {
        "llm_provider": llm.get("provider", "anthropic"),
        "deep_think_llm": llm.get("deep_think", "claude-opus-4-6"),
        "quick_think_llm": llm.get("quick_think", "claude-sonnet-4-20250514"),
        "max_debate_rounds": trading.get("max_debate_rounds", 2),
        "paper_mode": trading.get("mode", "paper") == "paper",
        "log_dir": log_cfg.get("log_dir", "cits/logs"),
        "analyst_temperature": llm.get("analyst_temperature", 0.3),
        "debate_temperature": llm.get("debate_temperature", 0.4),
        "trader_temperature": llm.get("trader_temperature", 0.2),
    }

    # Pass through structured sections for downstream consumers
    if trading.get("watchlist"):
        flat["watchlist"] = trading["watchlist"]
    if risk:
        flat["risk"] = risk
    if broker:
        flat["broker"] = broker

    return flat


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Override config values with environment variables when set."""
    env_map: dict[str, tuple[str, type]] = {
        "CITS_LLM_PROVIDER": ("llm_provider", str),
        "CITS_DEEP_THINK_LLM": ("deep_think_llm", str),
        "CITS_QUICK_THINK_LLM": ("quick_think_llm", str),
        "CITS_MAX_DEBATE_ROUNDS": ("max_debate_rounds", int),
        "CITS_LOG_DIR": ("log_dir", str),
    }

    for env_var, (key, cast) in env_map.items():
        value = os.environ.get(env_var)
        if value is not None:
            try:
                config[key] = cast(value)
                logger.debug("Config override from env: %s=%s", key, config[key])
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid value for %s=%r; keeping default", env_var, value
                )

    # Special handling: CITS_TRADING_MODE -> paper_mode bool
    mode = os.environ.get("CITS_TRADING_MODE")
    if mode is not None:
        config["paper_mode"] = mode.lower() == "paper"

    return config


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load CITS configuration from YAML and environment variables.

    Parameters
    ----------
    path : str | Path | None
        Path to ``config.yml``.  Defaults to ``cits/config.yml`` relative
        to this module.

    Returns
    -------
    dict
        Flat configuration dict compatible with
        :data:`TradingGraph.DEFAULT_CONFIG`.
    """
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH

    if not config_path.exists():
        logger.warning(
            "Config file not found at %s; using fallback defaults", config_path
        )
        return _apply_env_overrides({**_FALLBACK_CONFIG})

    try:
        import yaml  # lazy import so PyYAML is only required at load time

        with open(config_path) as fh:
            raw = yaml.safe_load(fh) or {}
        logger.info("Loaded config from %s", config_path)
    except Exception:
        logger.exception("Failed to read %s; using fallback defaults", config_path)
        return _apply_env_overrides({**_FALLBACK_CONFIG})

    flat = _flatten_yaml(raw)
    return _apply_env_overrides(flat)
