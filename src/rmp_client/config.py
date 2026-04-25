"""Configuration for the RateMyProfessors API client.

All client behavior (base URL, timeouts, retries, rate limiting) is driven
by :class:`RMPClientConfig`. Pass an instance to :class:`RMPClient`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

DEFAULT_BASE_URL = "https://www.ratemyprofessors.com/graphql"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"
)

DEFAULT_HEADERS: Mapping[str, str] = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept-Language": "en-US,en;q=0.5",
}


@dataclass(slots=True)
class RMPClientConfig:
    """Configuration for RMPClient.

    Build one and pass it to :class:`RMPClient`. Only override what you need;
    everything has sensible defaults.
    """

    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 10.0
    max_retries: int = 3
    user_agent: str = DEFAULT_USER_AGENT
    default_headers: Mapping[str, str] = field(
        default_factory=lambda: dict(DEFAULT_HEADERS)
    )
