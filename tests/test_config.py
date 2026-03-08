"""Tests for RMPClientConfig."""

from __future__ import annotations

import os

import pytest

from rmp_client.config import (
    DEFAULT_BASE_URL,
    DEFAULT_GET_HEADERS,
    DEFAULT_PROFESSOR_PAGE_BASE,
    RMPClientConfig,
)


class TestRMPClientConfigDefaults:
    """Default values and structure."""

    def test_default_base_url(self) -> None:
        config = RMPClientConfig()
        assert config.base_url == DEFAULT_BASE_URL

    def test_default_professor_page_base(self) -> None:
        config = RMPClientConfig()
        assert config.professor_page_base == DEFAULT_PROFESSOR_PAGE_BASE

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


class TestRMPClientConfigFromEnv:
    """from_env() reads environment variables."""

    def test_from_env_uses_defaults_when_env_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key in (
            "RMP_CLIENT_BASE_URL",
            "RMP_CLIENT_PROFESSOR_PAGE_BASE",
            "RMP_CLIENT_TIMEOUT_SECONDS",
            "RMP_CLIENT_MAX_RETRIES",
            "RMP_CLIENT_RATE_LIMIT_PER_MINUTE",
        ):
            monkeypatch.delenv(key, raising=False)
        config = RMPClientConfig.from_env()
        assert config.base_url == DEFAULT_BASE_URL
        assert config.professor_page_base == DEFAULT_PROFESSOR_PAGE_BASE
        assert config.timeout_seconds == 10.0
        assert config.max_retries == 3
        assert config.rate_limit_per_minute == 60

    def test_from_env_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RMP_CLIENT_BASE_URL", "https://custom.graphql")
        config = RMPClientConfig.from_env()
        assert config.base_url == "https://custom.graphql"

    def test_from_env_professor_page_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RMP_CLIENT_PROFESSOR_PAGE_BASE", "https://custom.site")
        config = RMPClientConfig.from_env()
        assert config.professor_page_base == "https://custom.site"

    def test_from_env_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RMP_CLIENT_TIMEOUT_SECONDS", "30")
        config = RMPClientConfig.from_env()
        assert config.timeout_seconds == 30.0

    def test_from_env_max_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RMP_CLIENT_MAX_RETRIES", "5")
        config = RMPClientConfig.from_env()
        assert config.max_retries == 5

    def test_from_env_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RMP_CLIENT_RATE_LIMIT_PER_MINUTE", "30")
        config = RMPClientConfig.from_env()
        assert config.rate_limit_per_minute == 30
