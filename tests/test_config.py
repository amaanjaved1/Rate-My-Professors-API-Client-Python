"""Tests for RMPClientConfig."""

from __future__ import annotations

from rmp_client.config import (
    DEFAULT_BASE_URL,
    DEFAULT_COMPARE_SCHOOLS_PAGE_URL,
    DEFAULT_GET_HEADERS,
    DEFAULT_PROFESSORS_PAGE_URL,
    DEFAULT_SCHOOLS_PAGE_URL,
    DEFAULT_SEARCH_PROFESSORS_PAGE_URL,
    DEFAULT_SEARCH_SCHOOLS_PAGE_URL,
    RMPClientConfig,
)


class TestRMPClientConfigDefaults:
    """Default values and structure."""

    def test_default_professors_page_url(self) -> None:
        config = RMPClientConfig()
        assert config.professors_page_url == DEFAULT_PROFESSORS_PAGE_URL

    def test_default_schools_page_url(self) -> None:
        config = RMPClientConfig()
        assert config.schools_page_url == DEFAULT_SCHOOLS_PAGE_URL

    def test_default_compare_schools_page_url(self) -> None:
        config = RMPClientConfig()
        assert config.compare_schools_page_url == DEFAULT_COMPARE_SCHOOLS_PAGE_URL

    def test_default_search_professors_page_url(self) -> None:
        config = RMPClientConfig()
        assert config.search_professors_page_url == DEFAULT_SEARCH_PROFESSORS_PAGE_URL

    def test_default_search_schools_page_url(self) -> None:
        config = RMPClientConfig()
        assert config.search_schools_page_url == DEFAULT_SEARCH_SCHOOLS_PAGE_URL

    def test_default_base_url(self) -> None:
        config = RMPClientConfig()
        assert config.base_url == DEFAULT_BASE_URL

    def test_default_headers_match_get_headers(self) -> None:
        config = RMPClientConfig()
        assert dict(config.default_headers) == dict(DEFAULT_GET_HEADERS)
        assert "User-Agent" in config.default_headers
        assert "Accept-Language" in config.default_headers

    def test_default_timeout_and_retries(self) -> None:
        config = RMPClientConfig()
        assert config.timeout_seconds == 10.0
        assert config.max_retries == 3
        assert config.rate_limit_per_minute == 60

    def test_user_agent_default(self) -> None:
        config = RMPClientConfig()
        assert config.user_agent == DEFAULT_GET_HEADERS["User-Agent"]
