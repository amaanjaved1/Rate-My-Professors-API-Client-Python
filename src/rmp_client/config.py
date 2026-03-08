from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

DEFAULT_BASE_URL = "https://www.ratemyprofessors.com/graphql"
DEFAULT_PROFESSORS_PAGE_URL = "https://www.ratemyprofessors.com/professor/"
DEFAULT_SCHOOLS_PAGE_URL = "https://www.ratemyprofessors.com/school/"
DEFAULT_COMPARE_SCHOOLS_PAGE_URL = "https://www.ratemyprofessors.com/compare/schools/"
DEFAULT_SEARCH_PROFESSORS_PAGE_URL = "https://www.ratemyprofessors.com/search/professors/"
DEFAULT_SEARCH_SCHOOLS_PAGE_URL = "https://www.ratemyprofessors.com/search/schools/"

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
    professors_page_url: str = DEFAULT_PROFESSORS_PAGE_URL
    schools_page_url: str = DEFAULT_SCHOOLS_PAGE_URL
    compare_schools_page_url: str = DEFAULT_COMPARE_SCHOOLS_PAGE_URL
    search_professors_page_url: str = DEFAULT_SEARCH_PROFESSORS_PAGE_URL
    search_schools_page_url: str = DEFAULT_SEARCH_SCHOOLS_PAGE_URL
    timeout_seconds: float = 10.0
    max_retries: int = 3
    rate_limit_per_minute: int = 60
    user_agent: str = DEFAULT_GET_HEADERS["User-Agent"]
    default_headers: Mapping[str, str] = field(
        default_factory=lambda: dict(DEFAULT_GET_HEADERS)
    )

