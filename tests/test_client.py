"""Tests for RMPClient with mocked GraphQL responses via pytest-httpx."""

from __future__ import annotations

import base64
import json
from datetime import date

import pytest
import pytest_httpx

from rmp_client import RMPClient
from rmp_client.config import RMPClientConfig
from rmp_client.errors import ParsingError


def _cfg() -> RMPClientConfig:
    return RMPClientConfig(rate_limit_per_minute=10000)


def _gql(data: dict) -> str:
    return json.dumps({"data": data})


# ---------------------------------------------------------------------------
# searchSchools
# ---------------------------------------------------------------------------


class TestSearchSchools:
    def test_returns_schools(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"search": {"schools": {
            "edges": [
                {"cursor": "c0", "node": {"id": "U2Nob29sLTIzMQ==", "legacyId": 231, "name": "CUNY Queens College", "city": "Queens", "state": "NY", "numRatings": 552, "avgRating": 0, "avgRatingRounded": 3.3}},
                {"cursor": "c1", "node": {"id": "U2Nob29sLTE0NjY=", "legacyId": 1466, "name": "Queen's University at Kingston", "city": "Kingston", "state": "ON", "numRatings": 460, "avgRating": 0, "avgRatingRounded": 4}},
            ],
            "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
            "resultCount": 19,
        }}}})
        with RMPClient(config=_cfg()) as client:
            result = client.search_schools("queen")
        assert len(result.schools) == 2
        assert result.schools[0].id == "231"
        assert result.schools[0].name == "CUNY Queens College"
        assert result.schools[0].location == "Queens, NY"
        assert result.schools[0].num_ratings == 552
        assert result.schools[0].overall_quality == 3.3
        assert result.schools[1].id == "1466"
        assert result.total == 19
        assert result.has_next_page is True
        assert result.next_cursor == "c1"

    def test_empty_result(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {}})
        with RMPClient(config=_cfg()) as client:
            result = client.search_schools("nonexistent")
        assert len(result.schools) == 0
        assert result.has_next_page is False

    def test_sends_correct_variables(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {}})
        with RMPClient(config=_cfg()) as client:
            client.search_schools("test", page_size=10, cursor="abc")
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["operationName"] == "SchoolSearchResultsPageQuery"
        assert body["variables"]["query"] == {"text": "test"}
        assert body["variables"]["count"] == 10
        assert body["variables"]["cursor"] == "abc"

    def test_multi_page_cursor_pagination(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"search": {"schools": {
            "edges": [{"cursor": "c0", "node": {"legacyId": 1, "name": "School A", "city": "A", "state": "AA", "numRatings": 10, "avgRatingRounded": 3.5}}],
            "pageInfo": {"hasNextPage": True, "endCursor": "c0"},
            "resultCount": 2,
        }}}})
        httpx_mock.add_response(json={"data": {"search": {"schools": {
            "edges": [{"cursor": "c1", "node": {"legacyId": 2, "name": "School B", "city": "B", "state": "BB", "numRatings": 20, "avgRatingRounded": 4.0}}],
            "pageInfo": {"hasNextPage": False, "endCursor": "c1"},
            "resultCount": 2,
        }}}})
        with RMPClient(config=_cfg()) as client:
            p1 = client.search_schools("test", page_size=1)
            assert p1.schools[0].name == "School A"
            assert p1.has_next_page is True
            p2 = client.search_schools("test", page_size=1, cursor=p1.next_cursor)
            assert p2.schools[0].name == "School B"
            assert p2.has_next_page is False
        assert len(httpx_mock.get_requests()) == 2


# ---------------------------------------------------------------------------
# searchProfessors
# ---------------------------------------------------------------------------


class TestSearchProfessors:
    def test_returns_professors(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"search": {"teachers": {
            "edges": [
                {"cursor": "c0", "node": {"legacyId": 1927792, "firstName": "Selim", "lastName": "Tuncel", "avgRating": 2.9, "numRatings": 35, "wouldTakeAgainPercent": 41.9355, "avgDifficulty": 4.3, "department": "Mathematics", "school": {"legacyId": 1530, "name": "University of Washington", "city": "Seattle", "state": "WA"}}},
                {"cursor": "c1", "node": {"legacyId": 336794, "firstName": "Selim", "lastName": "Kuru", "avgRating": 3.6, "numRatings": 25, "wouldTakeAgainPercent": 60, "avgDifficulty": 2.5, "department": "Languages", "school": {"legacyId": 1530, "name": "University of Washington", "city": "Seattle", "state": "WA"}}},
            ],
            "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
            "resultCount": 89,
        }}}})
        with RMPClient(config=_cfg()) as client:
            result = client.search_professors("selim")
        assert len(result.professors) == 2
        assert result.professors[0].id == "1927792"
        assert result.professors[0].name == "Selim Tuncel"
        assert result.professors[0].department == "Mathematics"
        assert result.professors[0].overall_rating == 2.9
        assert result.professors[0].school is not None
        assert result.professors[0].school.name == "University of Washington"
        assert result.professors[0].school.location == "Seattle, WA"
        assert result.total == 89
        assert result.has_next_page is True

    def test_passes_school_id(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {}})
        with RMPClient(config=_cfg()) as client:
            client.search_professors("test", school_id="1530")
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["variables"]["query"]["schoolID"] == "1530"

    def test_empty_result(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {}})
        with RMPClient(config=_cfg()) as client:
            result = client.search_professors("zzzzz")
        assert len(result.professors) == 0
        assert result.has_next_page is False

    def test_multi_page_cursor_pagination(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"search": {"teachers": {
            "edges": [{"cursor": "c0", "node": {"legacyId": 100, "firstName": "Alice", "lastName": "A", "avgRating": 4.0, "numRatings": 10, "department": "CS", "school": {"legacyId": 1, "name": "Uni", "city": "C", "state": "S"}}}],
            "pageInfo": {"hasNextPage": True, "endCursor": "c0"},
            "resultCount": 2,
        }}}})
        httpx_mock.add_response(json={"data": {"search": {"teachers": {
            "edges": [{"cursor": "c1", "node": {"legacyId": 200, "firstName": "Bob", "lastName": "B", "avgRating": 3.5, "numRatings": 5, "department": "Math", "school": {"legacyId": 1, "name": "Uni", "city": "C", "state": "S"}}}],
            "pageInfo": {"hasNextPage": False, "endCursor": "c1"},
            "resultCount": 2,
        }}}})
        with RMPClient(config=_cfg()) as client:
            p1 = client.search_professors("test", page_size=1)
            assert p1.professors[0].name == "Alice A"
            p2 = client.search_professors("test", page_size=1, cursor=p1.next_cursor)
            assert p2.professors[0].name == "Bob B"
            assert p2.has_next_page is False
        assert len(httpx_mock.get_requests()) == 2


# ---------------------------------------------------------------------------
# getProfessor
# ---------------------------------------------------------------------------


class TestGetProfessor:
    def test_returns_professor(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": {
            "legacyId": 2823076, "firstName": "Jane", "lastName": "Doe",
            "department": "Computer Science", "avgRating": 4.5, "avgDifficulty": 2.1,
            "numRatings": 42, "wouldTakeAgainPercent": 95.5,
            "school": {"legacyId": 123, "name": "MIT", "city": "Cambridge", "state": "MA"},
        }}})
        with RMPClient(config=_cfg()) as client:
            prof = client.get_professor("2823076")
        assert prof.id == "2823076"
        assert prof.name == "Jane Doe"
        assert prof.department == "Computer Science"
        assert prof.overall_rating == 4.5
        assert prof.level_of_difficulty == 2.1
        assert prof.num_ratings == 42
        assert prof.percent_take_again == 95.5
        assert prof.school is not None
        assert prof.school.name == "MIT"
        assert prof.school.location == "Cambridge, MA"

    def test_sends_base64_node_id(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": {"legacyId": 123, "lastName": "X"}}})
        with RMPClient(config=_cfg()) as client:
            client.get_professor("123")
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["variables"]["id"] == base64.b64encode(b"Teacher-123").decode()

    def test_raises_parsing_error_when_null(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": None}})
        with RMPClient(config=_cfg()) as client:
            with pytest.raises(ParsingError):
                client.get_professor("missing")


# ---------------------------------------------------------------------------
# getSchool
# ---------------------------------------------------------------------------


class TestGetSchool:
    def test_returns_school_with_summary(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": {
            "legacyId": 1466, "name": "Queen's University at Kingston",
            "city": "Kingston", "state": "ON", "country": "Canada",
            "numRatings": 460, "avgRatingRounded": 4,
            "summary": {
                "campusCondition": 4.17, "campusLocation": 4.03,
                "careerOpportunities": 4.0, "clubAndEventActivities": 4.01,
                "foodQuality": 3.27, "internetSpeed": 3.72,
                "schoolReputation": 4.42, "schoolSafety": 4.2,
                "schoolSatisfaction": 4.19, "socialActivities": 4.14,
            },
        }}})
        with RMPClient(config=_cfg()) as client:
            school = client.get_school("1466")
        assert school.id == "1466"
        assert school.name == "Queen's University at Kingston"
        assert school.location == "Kingston, ON, Canada"
        assert school.overall_quality == 4
        assert school.num_ratings == 460
        assert school.reputation == 4.42
        assert school.safety == 4.2
        assert school.happiness == 4.19
        assert school.facilities == 4.17
        assert school.social == 4.14
        assert school.location_rating == 4.03
        assert school.clubs == 4.01
        assert school.opportunities == 4.0
        assert school.internet == 3.72
        assert school.food == 3.27

    def test_raises_parsing_error_when_null(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": None}})
        with RMPClient(config=_cfg()) as client:
            with pytest.raises(ParsingError):
                client.get_school("999")

    def test_sends_base64_node_id(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": {"legacyId": 1466, "name": "Q"}}})
        with RMPClient(config=_cfg()) as client:
            client.get_school("1466")
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["variables"]["id"] == base64.b64encode(b"School-1466").decode()


# ---------------------------------------------------------------------------
# getCompareSchools
# ---------------------------------------------------------------------------


class TestGetCompareSchools:
    def test_returns_both_schools(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": {"legacyId": 1466, "name": "Queen's University", "city": "Kingston", "state": "ON", "numRatings": 460, "avgRatingRounded": 4}}})
        httpx_mock.add_response(json={"data": {"node": {"legacyId": 1491, "name": "Western University", "city": "London", "state": "ON", "numRatings": 889, "avgRatingRounded": 3.9}}})
        with RMPClient(config=_cfg()) as client:
            result = client.get_compare_schools("1466", "1491")
        assert result.school_1.name == "Queen's University"
        assert result.school_1.num_ratings == 460
        assert result.school_2.name == "Western University"
        assert result.school_2.num_ratings == 889
        assert len(httpx_mock.get_requests()) == 2


# ---------------------------------------------------------------------------
# getProfessorRatingsPage
# ---------------------------------------------------------------------------


def _ratings_page_response(comments: list[str], has_next: bool, end_cursor: str | None) -> dict:
    return {"data": {"node": {
        "__typename": "Teacher", "legacyId": 123, "lastName": "Smith",
        "numRatings": 100,
        "school": {"legacyId": 1, "name": "Uni", "city": "City", "state": "ST"},
        "ratings": {
            "edges": [{"cursor": f"cursor_{i}", "node": {
                "id": f"r{i}", "__typename": "Rating",
                "comment": c, "helpfulRating": 4, "clarityRating": 5,
                "difficultyRating": 3, "ratingTags": "Tough grader--Get ready to read",
                "date": "2025-01-15 00:00:00 +0000 UTC", "class": "CS 101",
            }} for i, c in enumerate(comments)],
            "pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor},
        },
    }}}


class TestGetProfessorRatingsPage:
    def test_fetches_and_caches(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json=_ratings_page_response(["A", "B", "C"], False, None))
        with RMPClient(config=_cfg()) as client:
            page = client.get_professor_ratings_page("123", page_size=2)
        assert page.professor.id == "123"
        assert page.professor.name == "Smith"
        assert len(page.ratings) == 2
        assert page.ratings[0].comment == "A"
        assert page.ratings[1].comment == "B"
        assert page.has_next_page is True
        assert page.next_cursor == "2"
        assert len(httpx_mock.get_requests()) == 1

    def test_serves_from_cache(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json=_ratings_page_response(["A", "B", "C", "D", "E"], False, None))
        with RMPClient(config=_cfg()) as client:
            p1 = client.get_professor_ratings_page("123", page_size=2)
            p2 = client.get_professor_ratings_page("123", cursor=p1.next_cursor, page_size=2)
            p3 = client.get_professor_ratings_page("123", cursor=p2.next_cursor, page_size=2)
        assert [r.comment for r in p1.ratings] == ["A", "B"]
        assert [r.comment for r in p2.ratings] == ["C", "D"]
        assert [r.comment for r in p3.ratings] == ["E"]
        assert p3.has_next_page is False
        assert len(httpx_mock.get_requests()) == 1

    def test_pre_fetches_multiple_pages(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json=_ratings_page_response(["A", "B"], True, "cursor1"))
        httpx_mock.add_response(json=_ratings_page_response(["C", "D"], False, None))
        with RMPClient(config=_cfg()) as client:
            page = client.get_professor_ratings_page("123", page_size=10)
        assert len(page.ratings) == 4
        assert [r.comment for r in page.ratings] == ["A", "B", "C", "D"]
        assert len(httpx_mock.get_requests()) == 2

    def test_parses_rating_tags(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json=_ratings_page_response(["A"], False, None))
        with RMPClient(config=_cfg()) as client:
            page = client.get_professor_ratings_page("123", page_size=10)
        assert page.ratings[0].tags == ["Tough grader", "Get ready to read"]

    def test_parses_quality_from_clarity(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json=_ratings_page_response(["A"], False, None))
        with RMPClient(config=_cfg()) as client:
            page = client.get_professor_ratings_page("123", page_size=10)
        assert page.ratings[0].quality == 5
        assert page.ratings[0].difficulty == 3
        assert page.ratings[0].course_raw == "CS 101"

    def test_repeated_first_page_from_cache(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json=_ratings_page_response(["A", "B"], False, None))
        with RMPClient(config=_cfg()) as client:
            client.get_professor_ratings_page("123")
            client.get_professor_ratings_page("123")
        assert len(httpx_mock.get_requests()) == 1


# ---------------------------------------------------------------------------
# getSchoolRatingsPage
# ---------------------------------------------------------------------------


def _school_ratings_response(count: int, has_next: bool, end_cursor: str | None) -> dict:
    edges = [{"cursor": f"c{i}", "node": {
        "id": f"sr{i}", "comment": f"Review {i}",
        "date": "2025-12-15 22:29:19 +0000 UTC",
        "reputationRating": 5, "locationRating": 4, "safetyRating": 5,
        "socialRating": 4, "opportunitiesRating": 5, "happinessRating": 5,
        "facilitiesRating": 5, "internetRating": 4, "foodRating": 3, "clubsRating": 5,
        "thumbsUpTotal": 2, "thumbsDownTotal": 1,
    }} for i in range(count)]
    return {"data": {"node": {
        "id": "U2Nob29sLTE0NjY=", "name": "Queen's University",
        "city": "Kingston", "state": "ON", "country": "Canada",
        "ratings": {"edges": edges, "pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor}},
    }}}


class TestGetSchoolRatingsPage:
    def test_fetches_and_caches(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json=_school_ratings_response(3, False, None))
        with RMPClient(config=_cfg()) as client:
            page = client.get_school_ratings_page("1466", page_size=2)
        assert page.school.name == "Queen's University"
        assert len(page.ratings) == 2
        assert page.has_next_page is True
        assert page.next_cursor == "2"

    def test_parses_category_ratings(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json=_school_ratings_response(1, False, None))
        with RMPClient(config=_cfg()) as client:
            page = client.get_school_ratings_page("1466", page_size=10)
        r = page.ratings[0]
        assert r.category_ratings is not None
        assert r.category_ratings["reputation"] == 5
        assert r.category_ratings["location"] == 4
        assert r.category_ratings["food"] == 3
        assert r.thumbs_up == 2
        assert r.thumbs_down == 1
        assert r.overall is not None and r.overall > 0

    def test_serves_from_cache(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json=_school_ratings_response(5, False, None))
        with RMPClient(config=_cfg()) as client:
            p1 = client.get_school_ratings_page("1466", page_size=2)
            p2 = client.get_school_ratings_page("1466", cursor=p1.next_cursor, page_size=2)
        assert len(p1.ratings) == 2
        assert len(p2.ratings) == 2
        assert len(httpx_mock.get_requests()) == 1

    def test_pre_fetches_multiple_pages(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json=_school_ratings_response(2, True, "c1"))
        httpx_mock.add_response(json=_school_ratings_response(2, False, None))
        with RMPClient(config=_cfg()) as client:
            page = client.get_school_ratings_page("1466", page_size=10)
        assert len(page.ratings) == 4
        assert len(httpx_mock.get_requests()) == 2


# ---------------------------------------------------------------------------
# iterProfessorRatings
# ---------------------------------------------------------------------------


class TestIterProfessorRatings:
    def test_yields_all(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": {
            "legacyId": 1, "lastName": "X", "numRatings": 3,
            "ratings": {"edges": [
                {"cursor": "c0", "node": {"comment": "A", "date": "2025-03-01", "clarityRating": 5, "difficultyRating": 2, "class": "CS"}},
                {"cursor": "c1", "node": {"comment": "B", "date": "2025-02-01", "clarityRating": 4, "difficultyRating": 3, "class": "CS"}},
                {"cursor": "c2", "node": {"comment": "C", "date": "2025-01-01", "clarityRating": 3, "difficultyRating": 4, "class": "CS"}},
            ], "pageInfo": {"hasNextPage": False, "endCursor": None}},
        }}})
        with RMPClient(config=_cfg()) as client:
            comments = [r.comment for r in client.iter_professor_ratings("1", page_size=10)]
        assert comments == ["A", "B", "C"]

    def test_stops_at_since_date(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": {
            "legacyId": 1, "lastName": "X", "numRatings": 2,
            "ratings": {"edges": [
                {"cursor": "c0", "node": {"comment": "New", "date": "2025-06-01", "clarityRating": 5, "difficultyRating": 2, "class": "CS"}},
                {"cursor": "c1", "node": {"comment": "Old", "date": "2024-01-01", "clarityRating": 4, "difficultyRating": 3, "class": "CS"}},
            ], "pageInfo": {"hasNextPage": False, "endCursor": None}},
        }}})
        with RMPClient(config=_cfg()) as client:
            since = date(2025, 1, 1)
            comments = [r.comment for r in client.iter_professor_ratings("1", since=since)]
        assert comments == ["New"]

    def test_small_page_size_across_cache(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": {
            "legacyId": 1, "lastName": "X", "numRatings": 5,
            "ratings": {"edges": [
                {"cursor": f"c{i}", "node": {"comment": f"R{i+1}", "date": f"2025-0{5-i}-01", "clarityRating": 5-i, "difficultyRating": i+1, "class": "CS"}}
                for i in range(5)
            ], "pageInfo": {"hasNextPage": False, "endCursor": None}},
        }}})
        with RMPClient(config=_cfg()) as client:
            comments = [r.comment for r in client.iter_professor_ratings("1", page_size=2)]
        assert comments == ["R1", "R2", "R3", "R4", "R5"]
        assert len(httpx_mock.get_requests()) == 1

    def test_multi_graphql_page_prefetch(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": {
            "legacyId": 1, "lastName": "X", "numRatings": 4,
            "ratings": {"edges": [
                {"cursor": "c0", "node": {"comment": "P1A", "date": "2025-04-01", "clarityRating": 5, "difficultyRating": 2, "class": "CS"}},
                {"cursor": "c1", "node": {"comment": "P1B", "date": "2025-03-01", "clarityRating": 4, "difficultyRating": 3, "class": "CS"}},
            ], "pageInfo": {"hasNextPage": True, "endCursor": "c1"}},
        }}})
        httpx_mock.add_response(json={"data": {"node": {
            "legacyId": 1, "lastName": "X", "numRatings": 4,
            "ratings": {"edges": [
                {"cursor": "c2", "node": {"comment": "P2A", "date": "2025-02-01", "clarityRating": 3, "difficultyRating": 4, "class": "CS"}},
                {"cursor": "c3", "node": {"comment": "P2B", "date": "2025-01-01", "clarityRating": 2, "difficultyRating": 5, "class": "CS"}},
            ], "pageInfo": {"hasNextPage": False, "endCursor": None}},
        }}})
        with RMPClient(config=_cfg()) as client:
            comments = [r.comment for r in client.iter_professor_ratings("1", page_size=2)]
        assert comments == ["P1A", "P1B", "P2A", "P2B"]
        assert len(httpx_mock.get_requests()) == 2


# ---------------------------------------------------------------------------
# iterSchoolRatings
# ---------------------------------------------------------------------------


class TestIterSchoolRatings:
    def test_yields_all(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": {
            "name": "Uni", "city": "C", "state": "S",
            "ratings": {"edges": [
                {"cursor": "c0", "node": {"comment": "Good", "date": "2025-12-01", "reputationRating": 5, "thumbsUpTotal": 1, "thumbsDownTotal": 0}},
                {"cursor": "c1", "node": {"comment": "Fine", "date": "2025-11-01", "reputationRating": 4, "thumbsUpTotal": 0, "thumbsDownTotal": 0}},
            ], "pageInfo": {"hasNextPage": False, "endCursor": None}},
        }}})
        with RMPClient(config=_cfg()) as client:
            comments = [r.comment for r in client.iter_school_ratings("1466")]
        assert comments == ["Good", "Fine"]

    def test_stops_at_since_date(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"node": {
            "name": "Uni", "city": "C", "state": "S",
            "ratings": {"edges": [
                {"cursor": "c0", "node": {"comment": "Recent", "date": "2025-06-01", "reputationRating": 5, "thumbsUpTotal": 0, "thumbsDownTotal": 0}},
                {"cursor": "c1", "node": {"comment": "Old", "date": "2024-01-01", "reputationRating": 3, "thumbsUpTotal": 0, "thumbsDownTotal": 0}},
            ], "pageInfo": {"hasNextPage": False, "endCursor": None}},
        }}})
        with RMPClient(config=_cfg()) as client:
            since = date(2025, 1, 1)
            comments = [r.comment for r in client.iter_school_ratings("1466", since=since)]
        assert comments == ["Recent"]


# ---------------------------------------------------------------------------
# listProfessorsForSchool
# ---------------------------------------------------------------------------


class TestListProfessorsForSchool:
    def test_passes_school_id(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {}})
        with RMPClient(config=_cfg()) as client:
            client.list_professors_for_school(1530)
        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["variables"]["query"]["schoolID"] == "1530"
        assert body["variables"]["query"]["text"] == ""

    def test_returns_professors(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"search": {"teachers": {
            "edges": [
                {"cursor": "c0", "node": {"legacyId": 10, "firstName": "John", "lastName": "Doe", "avgRating": 4.2, "numRatings": 30, "department": "CS", "school": {"legacyId": 1530, "name": "UW", "city": "Seattle", "state": "WA"}}},
                {"cursor": "c1", "node": {"legacyId": 20, "firstName": "Jane", "lastName": "Smith", "avgRating": 3.8, "numRatings": 15, "department": "Math", "school": {"legacyId": 1530, "name": "UW", "city": "Seattle", "state": "WA"}}},
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": "c1"},
            "resultCount": 2,
        }}}})
        with RMPClient(config=_cfg()) as client:
            result = client.list_professors_for_school(1530, page_size=10)
        assert len(result.professors) == 2
        assert result.professors[0].name == "John Doe"
        assert result.professors[1].name == "Jane Smith"

    def test_paginates_with_cursor(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"search": {"teachers": {
            "edges": [{"cursor": "c0", "node": {"legacyId": 10, "firstName": "A", "lastName": "Prof", "avgRating": 4.0, "numRatings": 5, "department": "CS", "school": {"legacyId": 1530, "name": "UW", "city": "Seattle", "state": "WA"}}}],
            "pageInfo": {"hasNextPage": True, "endCursor": "c0"},
            "resultCount": 2,
        }}}})
        httpx_mock.add_response(json={"data": {"search": {"teachers": {
            "edges": [{"cursor": "c1", "node": {"legacyId": 20, "firstName": "B", "lastName": "Prof", "avgRating": 3.5, "numRatings": 3, "department": "Math", "school": {"legacyId": 1530, "name": "UW", "city": "Seattle", "state": "WA"}}}],
            "pageInfo": {"hasNextPage": False, "endCursor": "c1"},
            "resultCount": 2,
        }}}})
        with RMPClient(config=_cfg()) as client:
            p1 = client.list_professors_for_school(1530, page_size=1)
            assert p1.professors[0].name == "A Prof"
            p2 = client.list_professors_for_school(1530, page_size=1, cursor=p1.next_cursor)
            assert p2.professors[0].name == "B Prof"
            assert p2.has_next_page is False


# ---------------------------------------------------------------------------
# iterProfessorsForSchool
# ---------------------------------------------------------------------------


class TestIterProfessorsForSchool:
    def test_single_page(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"search": {"teachers": {
            "edges": [
                {"cursor": "c0", "node": {"legacyId": 1, "firstName": "A", "lastName": "One", "avgRating": 4.0, "numRatings": 10, "department": "CS", "school": {"legacyId": 99, "name": "U", "city": "C", "state": "S"}}},
                {"cursor": "c1", "node": {"legacyId": 2, "firstName": "B", "lastName": "Two", "avgRating": 3.5, "numRatings": 5, "department": "Math", "school": {"legacyId": 99, "name": "U", "city": "C", "state": "S"}}},
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": "c1"},
            "resultCount": 2,
        }}}})
        with RMPClient(config=_cfg()) as client:
            names = [p.name for p in client.iter_professors_for_school(99)]
        assert names == ["A One", "B Two"]
        assert len(httpx_mock.get_requests()) == 1

    def test_multi_page(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"search": {"teachers": {
            "edges": [{"cursor": "c0", "node": {"legacyId": 1, "firstName": "Page1", "lastName": "Prof", "avgRating": 4.0, "numRatings": 10, "department": "CS", "school": {"legacyId": 99, "name": "U", "city": "C", "state": "S"}}}],
            "pageInfo": {"hasNextPage": True, "endCursor": "c0"},
            "resultCount": 3,
        }}}})
        httpx_mock.add_response(json={"data": {"search": {"teachers": {
            "edges": [
                {"cursor": "c1", "node": {"legacyId": 2, "firstName": "Page2A", "lastName": "Prof", "avgRating": 3.5, "numRatings": 5, "department": "Math", "school": {"legacyId": 99, "name": "U", "city": "C", "state": "S"}}},
                {"cursor": "c2", "node": {"legacyId": 3, "firstName": "Page2B", "lastName": "Prof", "avgRating": 4.5, "numRatings": 20, "department": "Bio", "school": {"legacyId": 99, "name": "U", "city": "C", "state": "S"}}},
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": "c2"},
            "resultCount": 3,
        }}}})
        with RMPClient(config=_cfg()) as client:
            names = [p.name for p in client.iter_professors_for_school(99, page_size=1)]
        assert names == ["Page1 Prof", "Page2A Prof", "Page2B Prof"]
        assert len(httpx_mock.get_requests()) == 2

    def test_empty(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {}})
        with RMPClient(config=_cfg()) as client:
            names = [p.name for p in client.iter_professors_for_school(99)]
        assert names == []


# ---------------------------------------------------------------------------
# rawQuery
# ---------------------------------------------------------------------------


class TestRawQuery:
    def test_forwards_payload(self, httpx_mock: pytest_httpx.HTTPXMock) -> None:
        httpx_mock.add_response(json={"data": {"custom": "result"}})
        with RMPClient(config=_cfg()) as client:
            result = client.raw_query({"query": "{ viewer { id } }"})
        assert result["data"]["custom"] == "result"


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    def test_safe_to_call_multiple_times(self) -> None:
        client = RMPClient(config=_cfg())
        client.close()
        client.close()
