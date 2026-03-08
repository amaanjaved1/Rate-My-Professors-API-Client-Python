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
        "location": "City, ST, USA",
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
            professors_page_url="https://www.ratemyprofessors.com/professor/",
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
            professors_page_url="https://www.ratemyprofessors.com/professor/",
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
        assert prof.school.location == "City, ST, USA"

    def test_raises_parsing_error_when_professor_not_in_store(
        self, httpx_mock: pytest_httpx.HTTPXMock
    ) -> None:
        config = RMPClientConfig(
            professors_page_url="https://www.ratemyprofessors.com/professor/",
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
            professors_page_url="https://www.ratemyprofessors.com/professor/",
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
            professors_page_url="https://www.ratemyprofessors.com/professor/",
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
            professors_page_url="https://www.ratemyprofessors.com/professor/",
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
    """_professor_page_url uses config.professors_page_url."""

    def test_builds_correct_url(self) -> None:
        config = RMPClientConfig(professors_page_url="https://site.com/professor/")
        client = RMPClient(config=config)
        url = client._professor_page_url("legacy-123")
        assert url == "https://site.com/professor/legacy-123"


class TestRMPClientSearchSchools:
    """search_schools fetches search page and parses __RELAY_STORE__."""

    def test_returns_schools_from_search_page(
        self, httpx_mock: pytest_httpx.HTTPXMock
    ) -> None:
        store = {
            "client:root": {"__id": "client:root", "newSearch": {"__ref": "client:root:newSearch"}},
            "client:root:newSearch": {
                "__id": "client:root:newSearch",
                "schools(after:\"\",first:5,query:{\"text\":\"queens\"})": {"__ref": "conn:schools"},
            },
            "conn:schools": {
                "__typename": "SchoolSearchConnectionConnection",
                "resultCount": 8,
                "edges": {"__refs": ["edge:0", "edge:1"]},
                "pageInfo": {"__ref": "conn:pageInfo"},
            },
            "conn:pageInfo": {"hasNextPage": True, "endCursor": "YXJyYXljb25uZWN0aW9uOjQ="},
            "edge:0": {"node": {"__ref": "S1"}},
            "edge:1": {"node": {"__ref": "S2"}},
            "S1": {
                "__typename": "School",
                "legacyId": 231,
                "name": "CUNY Queens College",
                "city": "Queens",
                "state": "NY",
                "numRatings": 551,
                "avgRatingRounded": 3.3,
                "id": "S1",
            },
            "S2": {
                "__typename": "School",
                "legacyId": 842,
                "name": "St. John's University - Jamaica/Queens",
                "city": "Queens",
                "state": "NY",
                "numRatings": 425,
                "avgRatingRounded": 3.5,
                "id": "S2",
            },
        }
        html = _html_with_store(store)
        config = RMPClientConfig(
            search_schools_page_url="https://www.ratemyprofessors.com/search/schools/",
            rate_limit_per_minute=1000,
        )
        httpx_mock.add_response(
            url="https://www.ratemyprofessors.com/search/schools?q=queens",
            text=html,
        )
        with RMPClient(config=config) as client:
            result = client.search_schools("queens")
        assert len(result.schools) == 2
        assert result.schools[0].name == "CUNY Queens College"
        assert result.schools[0].location == "Queens, NY"
        assert result.schools[0].num_ratings == 551
        assert result.schools[0].overall_quality == 3.3
        assert result.schools[1].name == "St. John's University - Jamaica/Queens"
        assert result.total == 8
        assert result.has_next_page is True
        assert result.next_cursor == "YXJyYXljb25uZWN0aW9uOjQ="


class TestRMPClientSearchProfessors:
    """search_professors fetches search page and parses __RELAY_STORE__."""

    def test_returns_professors_from_search_page(
        self, httpx_mock: pytest_httpx.HTTPXMock
    ) -> None:
        store = {
            "client:root": {"__id": "client:root", "newSearch": {"__ref": "client:root:newSearch"}},
            "client:root:newSearch": {
                "__id": "client:root:newSearch",
                "teachers(after:\"\",first:5,query:{\"text\":\"test\"})": {"__ref": "conn:teachers"},
            },
            "conn:teachers": {
                "__typename": "TeacherSearchConnectionConnection",
                "resultCount": 196,
                "edges": {"__refs": ["edge:0", "edge:1"]},
                "pageInfo": {"__ref": "conn:pageInfo"},
            },
            "conn:pageInfo": {"hasNextPage": True, "endCursor": "YXJyYXljb25uZWN0aW9uOjQ="},
            "edge:0": {"node": {"__ref": "T1"}},
            "edge:1": {"node": {"__ref": "T2"}},
            "T1": {
                "__typename": "Teacher",
                "legacyId": 2707318,
                "firstName": "Susan",
                "lastName": "Testani",
                "department": "Mathematics",
                "avgRating": 3.1,
                "numRatings": 9,
                "wouldTakeAgainPercent": 44.44,
                "avgDifficulty": 3,
                "school": {"__ref": "S1"},
            },
            "S1": {"__typename": "School", "id": "S1", "name": "Montgomery County Community College (all)"},
            "T2": {
                "__typename": "Teacher",
                "legacyId": 3079576,
                "firstName": "Kimberly",
                "lastName": "Testa Fortier",
                "department": "Education",
                "avgRating": 5,
                "numRatings": 1,
                "wouldTakeAgainPercent": 100,
                "avgDifficulty": 1,
                "school": {"__ref": "S2"},
            },
            "S2": {"__typename": "School", "id": "S2", "name": "Purdue University Global"},
        }
        html = _html_with_store(store)
        config = RMPClientConfig(
            search_professors_page_url="https://www.ratemyprofessors.com/search/professors/",
            rate_limit_per_minute=1000,
        )
        httpx_mock.add_response(
            url="https://www.ratemyprofessors.com/search/professors?q=test",
            text=html,
        )
        with RMPClient(config=config) as client:
            result = client.search_professors("test")
        assert len(result.professors) == 2
        assert result.professors[0].name == "Susan Testani"
        assert result.professors[0].department == "Mathematics"
        assert result.professors[0].overall_rating == 3.1
        assert result.professors[0].num_ratings == 9
        assert result.professors[0].school is not None
        assert result.professors[0].school.name == "Montgomery County Community College (all)"
        assert result.professors[1].name == "Kimberly Testa Fortier"
        assert result.total == 196
        assert result.has_next_page is True
        assert result.next_cursor == "YXJyYXljb25uZWN0aW9uOjQ="


class TestRMPClientGetCompareSchools:
    """get_compare_schools fetches compare page and returns both schools."""

    def test_returns_both_schools_from_compare_page(
        self, httpx_mock: pytest_httpx.HTTPXMock
    ) -> None:
        store = {
            "S1466": {
                "__typename": "School",
                "legacyId": 1466,
                "name": "Queen's University at Kingston",
                "location": "Kingston, ON",
                "numRatings": 460,
                "avgRatingRounded": 4,
                "summary": {"__ref": "sum1466"},
            },
            "sum1466": {
                "__typename": "SchoolSummary",
                "schoolReputation": 4.42,
                "schoolSafety": 4.2,
                "schoolSatisfaction": 4.19,
                "campusCondition": 4.17,
                "socialActivities": 4.14,
                "campusLocation": 4.03,
                "clubAndEventActivities": 4.01,
                "careerOpportunities": 4.0,
                "internetSpeed": 3.72,
                "foodQuality": 3.27,
            },
            "S1491": {
                "__typename": "School",
                "legacyId": 1491,
                "name": "Western University",
                "location": "London, ON",
                "numRatings": 889,
                "avgRatingRounded": 3.9,
                "summary": {"__ref": "sum1491"},
            },
            "sum1491": {
                "__typename": "SchoolSummary",
                "schoolReputation": 4.05,
                "schoolSafety": 4.11,
                "schoolSatisfaction": 4.07,
                "campusCondition": 4.14,
                "socialActivities": 4.14,
                "campusLocation": 3.79,
                "clubAndEventActivities": 4.05,
                "careerOpportunities": 3.75,
                "internetSpeed": 3.48,
                "foodQuality": 3.44,
            },
        }
        html = _html_with_store(store)
        config = RMPClientConfig(
            compare_schools_page_url="https://www.ratemyprofessors.com/compare/schools/",
            rate_limit_per_minute=1000,
        )
        httpx_mock.add_response(
            url="https://www.ratemyprofessors.com/compare/schools/1466/1491",
            text=html,
        )
        with RMPClient(config=config) as client:
            result = client.get_compare_schools("1466", "1491")
        assert result.school_1.name == "Queen's University at Kingston"
        assert result.school_1.num_ratings == 460
        assert result.school_1.overall_quality == 4.0
        assert result.school_1.reputation == 4.42
        assert result.school_2.name == "Western University"
        assert result.school_2.num_ratings == 889
        assert result.school_2.overall_quality == 3.9
        assert result.school_2.reputation == 4.05
