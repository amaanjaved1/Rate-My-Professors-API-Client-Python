from __future__ import annotations

from typing import Any, Optional


class RMPError(Exception):
    """Base exception for all errors raised by this library."""


class ConfigurationError(RMPError):
    """Raised when the client is misconfigured."""


class HttpError(RMPError):
    """HTTP transport-level error."""

    def __init__(self, status_code: int, url: str, body: Optional[str] = None) -> None:
        self.status_code = status_code
        self.url = url
        self.body = body
        super().__init__(f"HTTP {status_code} for {url}")


class RetryError(RMPError):
    """Raised when a request ultimately fails after exhausting retries."""

    def __init__(self, last_error: Exception) -> None:
        self.last_error = last_error
        super().__init__(f"Request failed after retries: {last_error!r}")


class RMPAPIError(RMPError):
    """Raised when the RMP API returns an application-level error (e.g. GraphQL errors)."""

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        self.details = details
        super().__init__(message)


class ParsingError(RMPError):
    """Raised when a response cannot be parsed into the expected model."""

