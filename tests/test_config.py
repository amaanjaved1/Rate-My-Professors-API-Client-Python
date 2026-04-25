"""Tests for RMPClientConfig."""

from __future__ import annotations

from rmp_client.config import (
    DEFAULT_BASE_URL,
    DEFAULT_HEADERS,
    DEFAULT_USER_AGENT,
    RMPClientConfig,
)


class TestRMPClientConfigDefaults:
    """Default values and structure."""

    def test_default_base_url(self) -> None:
        config = RMPClientConfig()
        assert config.base_url == DEFAULT_BASE_URL
        assert "graphql" in config.base_url

    def test_default_headers(self) -> None:
        config = RMPClientConfig()
        assert dict(config.default_headers) == dict(DEFAULT_HEADERS)
        assert "User-Agent" in config.default_headers
        assert "Accept-Language" in config.default_headers

    def test_default_timeout_and_retries(self) -> None:
        config = RMPClientConfig()
        assert config.timeout_seconds == 10.0
        assert config.max_retries == 3

    def test_user_agent_default(self) -> None:
        config = RMPClientConfig()
        assert config.user_agent == DEFAULT_USER_AGENT

    def test_override_base_url(self) -> None:
        config = RMPClientConfig(base_url="https://custom.example.com/graphql")
        assert config.base_url == "https://custom.example.com/graphql"

    def test_override_max_retries(self) -> None:
        config = RMPClientConfig(max_retries=5)
        assert config.max_retries == 5
