"""Tests for HttpClient (post_json) with mocked HTTP."""

from __future__ import annotations

import json

import pytest
import pytest_httpx

from rmp_client.config import RMPClientConfig
from rmp_client.errors import HttpError, RMPAPIError, RetryError
from rmp_client.http import HttpClient


class TestHttpClientPostJson:
    """post_json with pytest-httpx."""

    def test_returns_json_on_200(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        config = RMPClientConfig()
        payload = {"data": {"x": 1}}
        httpx_mock.add_response(
            url=config.base_url,
            json=payload,
        )
        client = HttpClient(config)
        try:
            result = client.post_json("", {"query": "..."})
            assert result == payload
        finally:
            client.close()

    def test_raises_rmp_api_error_when_errors_in_body(
        self, httpx_mock: pytest_httpx.HTTPXMock
    ) -> None:
        config = RMPClientConfig()
        body = json.dumps({"errors": [{"message": "Unauthorized"}]})
        httpx_mock.add_response(url=config.base_url, content=body.encode(), status_code=200)
        client = HttpClient(config)
        try:
            with pytest.raises(RMPAPIError) as exc_info:
                client.post_json("", {"query": "..."})
            assert exc_info.value.details == [{"message": "Unauthorized"}]
        finally:
            client.close()

    def test_raises_http_error_on_4xx(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        config = RMPClientConfig()
        httpx_mock.add_response(url=config.base_url, status_code=403, text="Forbidden")
        client = HttpClient(config)
        try:
            with pytest.raises(HttpError) as exc_info:
                client.post_json("", {})
            assert exc_info.value.status_code == 403
        finally:
            client.close()

    def test_retries_on_5xx(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        config = RMPClientConfig(max_retries=2)
        httpx_mock.add_response(url=config.base_url, status_code=502)
        httpx_mock.add_response(url=config.base_url, status_code=502)
        httpx_mock.add_response(url=config.base_url, status_code=502)
        client = HttpClient(config)
        try:
            with pytest.raises(HttpError) as exc_info:
                client.post_json("", {})
            assert exc_info.value.status_code == 502
            assert len(httpx_mock.get_requests()) >= 2
        finally:
            client.close()

    def test_succeeds_after_5xx_retry(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        config = RMPClientConfig(max_retries=3)
        httpx_mock.add_response(url=config.base_url, status_code=503)
        httpx_mock.add_response(url=config.base_url, json={"data": "ok"})
        client = HttpClient(config)
        try:
            result = client.post_json("", {})
            assert result == {"data": "ok"}
        finally:
            client.close()

    def test_retries_on_429(
        self, httpx_mock: pytest_httpx.HTTPXMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("rmp_client.http.time.sleep", lambda _: None)
        config = RMPClientConfig(max_retries=1)
        httpx_mock.add_response(url=config.base_url, status_code=429)
        httpx_mock.add_response(url=config.base_url, json={"data": "ok"})
        client = HttpClient(config)
        try:
            result = client.post_json("", {})
            assert result == {"data": "ok"}
            assert len(httpx_mock.get_requests()) == 2
        finally:
            client.close()

    def test_sends_default_headers(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        config = RMPClientConfig()
        httpx_mock.add_response(url=config.base_url, json={"data": {}})
        client = HttpClient(config)
        try:
            client.post_json("", {"query": "..."})
            requests = httpx_mock.get_requests()
            assert len(requests) >= 1
            request = requests[0]
            assert "User-Agent" in request.headers
            assert "Accept-Language" in request.headers
        finally:
            client.close()
