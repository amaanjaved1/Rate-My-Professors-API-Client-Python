"""Tests for error classes."""

from __future__ import annotations

import pytest

from rmp_client.errors import (
    ConfigurationError,
    HttpError,
    ParsingError,
    RMPAPIError,
    RMPError,
    RateLimitError,
    RetryError,
)


class TestRMPErrorHierarchy:
    """All errors inherit from RMPError."""

    def test_configuration_error_is_rmp_error(self) -> None:
        assert issubclass(ConfigurationError, RMPError)
        exc = ConfigurationError("bad config")
        assert isinstance(exc, RMPError)

    def test_http_error_is_rmp_error(self) -> None:
        assert issubclass(HttpError, RMPError)
        exc = HttpError(404, "http://example.com", body="")
        assert isinstance(exc, RMPError)

    def test_parsing_error_is_rmp_error(self) -> None:
        assert issubclass(ParsingError, RMPError)
        exc = ParsingError("bad payload")
        assert isinstance(exc, RMPError)

    def test_rmp_api_error_is_rmp_error(self) -> None:
        assert issubclass(RMPAPIError, RMPError)
        exc = RMPAPIError("api err", details=[])
        assert isinstance(exc, RMPError)

    def test_rate_limit_error_is_rmp_error(self) -> None:
        assert issubclass(RateLimitError, RMPError)
        exc = RateLimitError("limit exceeded")
        assert isinstance(exc, RMPError)

    def test_retry_error_is_rmp_error(self) -> None:
        assert issubclass(RetryError, RMPError)
        exc = RetryError(ValueError("inner"))
        assert isinstance(exc, RMPError)


class TestHttpError:
    """HttpError stores status_code, url, body."""

    def test_attributes(self) -> None:
        err = HttpError(404, "https://example.com/foo", body="Not Found")
        assert err.status_code == 404
        assert err.url == "https://example.com/foo"
        assert err.body == "Not Found"

    def test_message(self) -> None:
        err = HttpError(500, "https://api.test/")
        assert "500" in str(err)
        assert "https://api.test/" in str(err)

    def test_body_optional(self) -> None:
        err = HttpError(403, "https://x.com")
        assert err.body is None


class TestRetryError:
    """RetryError wraps last_error."""

    def test_last_error(self) -> None:
        inner = ConnectionError("failed")
        err = RetryError(inner)
        assert err.last_error is inner
        assert "retries" in str(err).lower() or "failed" in str(err)


class TestRMPAPIError:
    """RMPAPIError stores details."""

    def test_details(self) -> None:
        details = [{"message": "Unauthorized"}]
        err = RMPAPIError("API error", details=details)
        assert err.details == details

    def test_details_optional(self) -> None:
        err = RMPAPIError("Generic error")
        assert err.details is None


class TestParsingError:
    """ParsingError is used for response parse failures."""

    def test_message(self) -> None:
        err = ParsingError("Unexpected payload shape")
        assert "Unexpected" in str(err)


class TestRateLimitError:
    """RateLimitError for local rate limit."""

    def test_message(self) -> None:
        err = RateLimitError("Local rate limit exceeded")
        assert "rate limit" in str(err).lower()
