from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional
import os


DEFAULT_BASE_URL = "https://www.ratemyprofessors.com/graphql"


@dataclass(slots=True)
class RMPClientConfig:
    """Configuration for RMPClient.

    This is deliberately small and serialisable so you can stash it in settings.
    """

    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 10.0
    max_retries: int = 3
    rate_limit_per_minute: int = 60
    user_agent: str = "ratemyprofessors-client/0.1.0"
    default_headers: Mapping[str, str] = field(
        default_factory=lambda: {
            "User-Agent": "ratemyprofessors-client/0.1.0",
            "Referer": "https://www.ratemyprofessors.com/",
            "Accept": "application/json",
        }
    )

    @classmethod
    def from_env(cls) -> "RMPClientConfig":
        """Build config from environment variables where present."""
        base_url = os.getenv("RMP_CLIENT_BASE_URL", DEFAULT_BASE_URL)
        timeout_raw = os.getenv("RMP_CLIENT_TIMEOUT_SECONDS")
        retries_raw = os.getenv("RMP_CLIENT_MAX_RETRIES")
        rate_raw = os.getenv("RMP_CLIENT_RATE_LIMIT_PER_MINUTE")

        timeout = float(timeout_raw) if timeout_raw is not None else 10.0
        max_retries = int(retries_raw) if retries_raw is not None else 3
        rate_limit_per_minute = int(rate_raw) if rate_raw is not None else 60

        return cls(
            base_url=base_url,
            timeout_seconds=timeout,
            max_retries=max_retries,
            rate_limit_per_minute=rate_limit_per_minute,
        )

