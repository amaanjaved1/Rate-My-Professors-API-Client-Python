"""Tests for RMPClient (get_professor, ratings, parsing) with mocked HTTP."""

from __future__ import annotations

import json
from datetime import date
import pytest
import pytest_httpx

from rmp_client import RMPClient
from rmp_client.config import RMPClientConfig
from rmp_client.errors import ParsingError


def _html_with_store(store: dict) -> str:
    return f'<html><script>window.__RELAY_STORE__ = {json.dumps(store)};</script></html>'


def _make_professor_store(professor_id: str, name: str = "Test Professor", **kwargs: object) -> dict:
    """Minimal Relay store with one Professor and optional school/ratings."""
    prof_node = {
        "__typename": "Professor",
        "id": professor_id,
        "legacyId": professor_id,
        "name": name,
        "overallRating": 4.5,
        "numRatings": 10,
        **kwargs,
    }
    store: dict = {f"node:{professor_id}": prof_node}
    return store


def _add_school_to_store(store: dict, prof_key: str, school_id: str = "s1") -> None:
    store["node:s1"] = {
        "__typename": "School",
        "id": school_id,
        "name": "Test University",
        "city": "City",
        "state": "ST",
        "country": "USA",
    }
    store[prof_key]["school"] = {"__ref": "node:s1"}


def _add_ratings_to_store(
    store: dict, prof_key: str, rating_comments: list[str]
) -> None:
    edges = []
    for i, comment in enumerate(rating_comments):
        rid = f"node:r{i}"
        store[rid] = {
            "__typename": "Rating",
            "id": rid,
            "comment": comment,
            "date": "2024-01-15",
            "quality": 5.0,
            "difficulty": 2.0,
            "course": "MATH 101",
        }
        edges.append({"node": {"__ref": rid}})
    conn_id = "conn:ratings"
    store[conn_id] = {"edges": edges}
    store[prof_key]["ratings"] = {"__ref": conn_id}


class TestRMPClientGetProfessor:
    """get_professor fetches page and parses __RELAY_STORE__."""

    def test_returns_professor_from_relay_store(
        self, httpx_mock: pytest_httpx.HTTPXMock
    ) -> None:
        config = RMPClientConfig(
            professor_page_base="https://www.ratemyprofessors.com",
            rate_limit_per_minute=1000,
        )
        store = _make_professor_store("abc123", name="Jane Doe", department="Math")
        html = _html_with_store(store)
        httpx_mock.add_response(
            url="https://www.ratemyprofessors.com/professor/abc123",
            text=html,
        )
        with RMPClient(config=config) as client:
            prof = client.get_professor("abc123")
        assert prof.id == "abc123"
        assert prof.name == "Jane Doe"
        assert prof.department == "Math"
        assert prof.overall_rating == 4.5
        assert prof.num_ratings == 10

    def test_resolves_school_ref(
        self, httpx_mock: pytest_httpx.HTTPXMock
    ) -> None:
        config = RMPClientConfig(
            professor_page_base="https://www.ratemyprofessors.com",
            rate_limit_per_minute=1000,
        )
        store = _make_professor_store("p1")
        _add_school_to_store(store, "node:p1")
        html = _html_with_store(store)
        httpx_mock.add_response(
            url="https://www.ratemyprofessors.com/professor/p1",
            text=html,
        )
        with RMPClient(config=config) as client:
            prof = client.get_professor("p1")
        assert prof.school is not None
        assert prof.school.name == "Test University"
        assert prof.school.city == "City"
        assert prof.school.state == "ST"
        assert prof.school.country == "USA"

    def test_raises_parsing_error_when_professor_not_in_store(
        self, httpx_mock: pytest_httpx.HTTPXMock
    ) -> None:
        config = RMPClientConfig(
            professor_page_base="https://www.ratemyprofessors.com",
            rate_limit_per_minute=1000,
        )
        store = {"client:root": {"__id": "client:root"}}  # no Professor
        html = _html_with_store(store)
        httpx_mock.add_response(
            url="https://www.ratemyprofessors.com/professor/missing",
            text=html,
        )
        with RMPClient(config=config) as client:
            with pytest.raises(ParsingError, match="not found"):
                client.get_professor("missing")

    def test_raises_parsing_error_when_store_missing_in_html(
        self, httpx_mock: pytest_httpx.HTTPXMock
    ) -> None:
        config = RMPClientConfig(
            professor_page_base="https://www.ratemyprofessors.com",
            rate_limit_per_minute=1000,
        )
        httpx_mock.add_response(
            url="https://www.ratemyprofessors.com/professor/x",
            text="<html><body>No store here</body></html>",
        )
        with RMPClient(config=config) as client:
            with pytest.raises(ParsingError, match="__RELAY_STORE__"):
                client.get_professor("x")


class TestRMPClientGetProfessorRatingsPage:
    """get_professor_ratings_page returns professor and ratings from store."""

    def test_returns_ratings_from_store(
        self, httpx_mock: pytest_httpx.HTTPXMock
    ) -> None:
        config = RMPClientConfig(
            professor_page_base="https://www.ratemyprofessors.com",
            rate_limit_per_minute=1000,
        )
        store = _make_professor_store("p1", name="Dr. Smith")
        _add_ratings_to_store(store, "node:p1", ["Great!", "Okay.", "Loved it"])
        html = _html_with_store(store)
        httpx_mock.add_response(
            url="https://www.ratemyprofessors.com/professor/p1",
            text=html,
        )
        with RMPClient(config=config) as client:
            page = client.get_professor_ratings_page("p1", page_size=10)
        assert page.professor.name == "Dr. Smith"
        assert len(page.ratings) == 3
        assert page.ratings[0].comment == "Great!"
        assert page.ratings[1].comment == "Okay."
        assert page.ratings[2].comment == "Loved it"
        assert page.ratings[0].date == date(2024, 1, 15)
        assert page.ratings[0].course_raw == "MATH 101"

    def test_pagination_in_memory(
        self, httpx_mock: pytest_httpx.HTTPXMock
    ) -> None:
        config = RMPClientConfig(
            professor_page_base="https://www.ratemyprofessors.com",
            rate_limit_per_minute=1000,
        )
        store = _make_professor_store("p1")
        _add_ratings_to_store(store, "node:p1", ["A", "B", "C", "D", "E"])
        html = _html_with_store(store)
        # Same page is fetched for each call to get_professor_ratings_page
        httpx_mock.add_response(
            url="https://www.ratemyprofessors.com/professor/p1",
            text=html,
            is_reusable=True,
        )
        with RMPClient(config=config) as client:
            page1 = client.get_professor_ratings_page("p1", page_size=2)
            page2 = client.get_professor_ratings_page(
                "p1", cursor=page1.next_cursor, page_size=2
            )
        assert len(page1.ratings) == 2
        assert page1.ratings[0].comment == "A"
        assert page1.ratings[1].comment == "B"
        assert page1.has_next_page is True
        assert len(page2.ratings) == 2
        assert page2.ratings[0].comment == "C"
        assert page2.ratings[1].comment == "D"


class TestRMPClientProfessorPageUrl:
    """_professor_page_url uses config.professor_page_base."""

    def test_builds_correct_url(self) -> None:
        config = RMPClientConfig(professor_page_base="https://site.com")
        client = RMPClient(config=config)
        url = client._professor_page_url("legacy-123")
        assert url == "https://site.com/professor/legacy-123"
