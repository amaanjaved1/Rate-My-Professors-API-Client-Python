"""HTTP client with retries, rate limiting, and error mapping."""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

import httpx

from .config import RMPClientConfig
from .errors import HttpError, RetryError, RMPAPIError
from .rate_limit import TokenBucket


class HttpClient:
    """Thin wrapper over httpx.Client adding retries, rate limiting, and error mapping."""

    def __init__(self, config: RMPClientConfig) -> None:
        self._config = config
        self._client = httpx.Client(timeout=config.timeout_seconds)
        self._bucket = TokenBucket(
            capacity=config.rate_limit_per_minute,
            refill_per_second=config.rate_limit_per_minute / 60.0,
        )

    def close(self) -> None:
        self._client.close()

    def _headers(self, extra: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
        headers: Dict[str, str] = dict(self._config.default_headers)
        headers.setdefault("User-Agent", self._config.user_agent)
        if extra:
            headers.update(extra)
        return headers

    def post_json(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        """POST JSON to ``base_url + path`` with retries and rate limiting."""
        url = (
            self._config.base_url
            if path == ""
            else f"{self._config.base_url.rstrip('/')}/{path.lstrip('/')}"
        )
        attempt = 0
        last_exc: Optional[Exception] = None

        while attempt <= self._config.max_retries:
            attempt += 1
            self._bucket.consume()
            try:
                response = self._client.post(
                    url,
                    json=payload,
                    headers=self._headers(headers),
                )
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt > self._config.max_retries:
                    raise RetryError(exc)
                continue

            if 200 <= response.status_code < 300:
                try:
                    data = response.json()
                except json.JSONDecodeError as exc:
                    raise HttpError(
                        response.status_code, str(response.url), body=response.text
                    ) from exc
                if isinstance(data, dict) and "errors" in data:
                    raise RMPAPIError(
                        "RMP API returned errors", details=data["errors"]
                    )
                return data  # type: ignore[return-value]

            err = HttpError(
                response.status_code, str(response.url), body=response.text
            )
            last_exc = err
            if (
                500 <= response.status_code < 600
                and attempt <= self._config.max_retries
            ):
                continue
            raise err

        assert last_exc is not None
        raise RetryError(last_exc)


class HttpClientContext:
    """Context-manager facade for HttpClient."""

    def __init__(self, config: RMPClientConfig) -> None:
        self._config = config
        self._client: Optional[HttpClient] = None

    def __enter__(self) -> HttpClient:
        self._client = HttpClient(self._config)
        return self._client

    def __exit__(self, *_: Any) -> None:
        assert self._client is not None
        self._client.close()
