# Configuration and settings for the backend SDK
#
# This module intentionally avoids a dependency on pydantic-settings to keep
# the runtime light. We use a small dataclass and a cached factory function that
# reads values from environment variables.

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


# Helper to fetch the first-present environment variable among several keys
# (e.g., support both UPPERCASE and lowercase variants)
_def_true = {"1", "true", "yes", "y", "on"}
_def_false = {"0", "false", "no", "n", "off"}


def _get_env_any(keys: list[str], default: Optional[str] = None) -> Optional[str]:
    for k in keys:
        v = os.getenv(k)
        if v is not None:
            return v
    return default


def _get_bool(keys: list[str], default: bool) -> bool:
    raw = _get_env_any(keys)
    if raw is None:
        return default
    lower = raw.strip().lower()
    if lower in _def_true:
        return True
    if lower in _def_false:
        return False
    # Fallback: any non-empty value -> True
    return bool(lower)


def _get_int(keys: list[str], default: int) -> int:
    raw = _get_env_any(keys)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _get_float(keys: list[str], default: float) -> float:
    raw = _get_env_any(keys)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    """Runtime configuration for the backend SDK.

    Environment variables (case-insensitive aliases shown):
    - ENVIRONMENT / environment
    - HYPERSYNC_API_URL / hypersync_api_url
    - HYPERSYNC_API_TOKEN / hypersync_api_token
    - BACKEND_API_KEY / backend_api_key
    - REQUEST_TIMEOUT_SECONDS / request_timeout_seconds
    - REQUEST_VERIFY_TLS / request_verify_tls
    - LARGE_TRANSFER_THRESHOLD / large_transfer_threshold
    - HIGH_FREQUENCY_THRESHOLD / high_frequency_threshold
    - CONCENTRATION_SHARE_THRESHOLD / concentration_share_threshold
    """

    # General
    environment: str = "development"

    # HyperSync connection
    hypersync_api_url: str = "https://fuel-testnet.hypersync.xyz/query"
    hypersync_api_token: Optional[str] = None

    # Optional API key to guard endpoints (used by FastAPI security module)
    backend_api_key: Optional[str] = None

    # HTTP behavior
    request_timeout_seconds: int = 30
    request_verify_tls: bool = True

    # Analysis thresholds
    large_transfer_threshold: float = 100_000.0
    high_frequency_threshold: int = 50
    concentration_share_threshold: float = 0.20


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from environment with sensible defaults.

    Values are cached for the process lifetime. Clear the cache if you need to
    pick up changes (get_settings.cache_clear()).
    """
    return Settings(
        environment=_get_env_any(["ENVIRONMENT", "environment"], "development") or "development",
        hypersync_api_url=_get_env_any(
            ["HYPERSYNC_API_URL", "hypersync_api_url"], "https://fuel-testnet.hypersync.xyz/query"
        )
        or "https://fuel-testnet.hypersync.xyz/query",
        hypersync_api_token=_get_env_any(["HYPERSYNC_API_TOKEN", "hypersync_api_token"], None),
        backend_api_key=_get_env_any(["BACKEND_API_KEY", "backend_api_key"], None),
        request_timeout_seconds=_get_int(["REQUEST_TIMEOUT_SECONDS", "request_timeout_seconds"], 30),
        request_verify_tls=_get_bool(["REQUEST_VERIFY_TLS", "request_verify_tls"], True),
        large_transfer_threshold=_get_float(["LARGE_TRANSFER_THRESHOLD", "large_transfer_threshold"], 100_000.0),
        high_frequency_threshold=_get_int(["HIGH_FREQUENCY_THRESHOLD", "high_frequency_threshold"], 50),
        concentration_share_threshold=_get_float(
            ["CONCENTRATION_SHARE_THRESHOLD", "concentration_share_threshold"], 0.20
        ),
    )
