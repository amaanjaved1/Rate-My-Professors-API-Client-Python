from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional
import os


DEFAULT_BASE_URL = "https://www.ratemyprofessors.com/graphql"
DEFAULT_PROFESSOR_PAGE_BASE = "https://www.ratemyprofessors.com"

# Headers used for GET requests (e.g. professor page HTML). RMP uses server-side rendering.
DEFAULT_GET_HEADERS: Mapping[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Accept-Language": "en-US,en;q=0.5",
}


@dataclass(slots=True)
class RMPClientConfig:
    """Configuration for RMPClient.

    This is deliberately small and serialisable so you can stash it in settings.
    """

    base_url: str = DEFAULT_BASE_URL
    professor_page_base: str = DEFAULT_PROFESSOR_PAGE_BASE
    timeout_seconds: float = 10.0
    max_retries: int = 3
    rate_limit_per_minute: int = 60
    user_agent: str = DEFAULT_GET_HEADERS["User-Agent"]
    default_headers: Mapping[str, str] = field(
        default_factory=lambda: dict(DEFAULT_GET_HEADERS)
    )

    @classmethod
    def from_env(cls) -> "RMPClientConfig":
        """Build config from environment variables where present."""
        base_url = os.getenv("RMP_CLIENT_BASE_URL", DEFAULT_BASE_URL)
        professor_base = os.getenv(
            "RMP_CLIENT_PROFESSOR_PAGE_BASE", DEFAULT_PROFESSOR_PAGE_BASE
        )
        timeout_raw = os.getenv("RMP_CLIENT_TIMEOUT_SECONDS")
        retries_raw = os.getenv("RMP_CLIENT_MAX_RETRIES")
        rate_raw = os.getenv("RMP_CLIENT_RATE_LIMIT_PER_MINUTE")

        timeout = float(timeout_raw) if timeout_raw is not None else 10.0
        max_retries = int(retries_raw) if retries_raw is not None else 3
        rate_limit_per_minute = int(rate_raw) if rate_raw is not None else 60

        return cls(
            base_url=base_url,
            professor_page_base=professor_base,
            timeout_seconds=timeout,
            max_retries=max_retries,
            rate_limit_per_minute=rate_limit_per_minute,
        )

