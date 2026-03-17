"""Integration tests for RMPClient against the live RateMyProfessors GraphQL API.

These tests make real HTTP requests. Run with a reasonable rate limit to
avoid hammering the API. Data assertions are kept flexible since live
data (num_ratings, etc.) changes over time.
"""

from __future__ import annotations

from datetime import date

import pytest

from rmp_client import RMPClient
from rmp_client.config import RMPClientConfig
from rmp_client.errors import ParsingError, RMPAPIError

SCHOOL_QUEENS = "1466"
SCHOOL_WESTERN = "1491"
SCHOOL_UW = "1530"
PROFESSOR_ID = "2823076"


@pytest.fixture(scope="module")
def client() -> RMPClient:
    cfg = RMPClientConfig(rate_limit_per_minute=30)
    c = RMPClient(config=cfg)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# search_schools
# ---------------------------------------------------------------------------


class TestSearchSchools:
    def test_returns_results(self, client: RMPClient) -> None:
        result = client.search_schools("queens")
        assert len(result.schools) > 0
        school = result.schools[0]
        assert school.id
        assert school.name
        assert school.location

    def test_pagination_fields(self, client: RMPClient) -> None:
        result = client.search_schools("university", page_size=2)
        assert result.page_size <= 2
        assert isinstance(result.has_next_page, bool)
        if result.has_next_page:
            assert result.next_cursor is not None

    def test_multi_page_cursor_pagination(self, client: RMPClient) -> None:
        p1 = client.search_schools("university", page_size=2)
        assert len(p1.schools) > 0
        assert p1.has_next_page is True
        assert p1.next_cursor is not None

        p2 = client.search_schools("university", page_size=2, cursor=p1.next_cursor)
        assert len(p2.schools) > 0
        p1_ids = {s.id for s in p1.schools}
        p2_ids = {s.id for s in p2.schools}
        assert p1_ids.isdisjoint(p2_ids), "Page 2 should not repeat page 1 schools"

    def test_empty_search(self, client: RMPClient) -> None:
        result = client.search_schools("zzzxxx999qqq")
        assert len(result.schools) == 0
        assert result.has_next_page is False


# ---------------------------------------------------------------------------
# search_professors
# ---------------------------------------------------------------------------


class TestSearchProfessors:
    def test_returns_results(self, client: RMPClient) -> None:
        result = client.search_professors("smith")
        assert len(result.professors) > 0
        prof = result.professors[0]
        assert prof.id
        assert prof.name

    def test_school_id_filter(self, client: RMPClient) -> None:
        result = client.search_professors("smith", school_id=SCHOOL_UW)
        assert len(result.professors) > 0
        for prof in result.professors:
            if prof.school:
                assert prof.school.id == SCHOOL_UW

    def test_multi_page_cursor_pagination(self, client: RMPClient) -> None:
        p1 = client.search_professors("smith", page_size=2)
        assert len(p1.professors) > 0
        assert p1.has_next_page is True
        assert p1.next_cursor is not None

        p2 = client.search_professors("smith", page_size=2, cursor=p1.next_cursor)
        assert len(p2.professors) > 0
        p1_ids = {p.id for p in p1.professors}
        p2_ids = {p.id for p in p2.professors}
        assert p1_ids.isdisjoint(p2_ids), "Page 2 should not repeat page 1 professors"

    def test_empty_search(self, client: RMPClient) -> None:
        result = client.search_professors("zzzxxx999qqq")
        assert len(result.professors) == 0
        assert result.has_next_page is False


# ---------------------------------------------------------------------------
# get_professor
# ---------------------------------------------------------------------------


class TestGetProfessor:
    def test_returns_professor(self, client: RMPClient) -> None:
        prof = client.get_professor(PROFESSOR_ID)
        assert prof.id == PROFESSOR_ID
        assert prof.name
        assert len(prof.name) > 0
        assert prof.department is not None
        assert prof.overall_rating is not None
        assert prof.num_ratings is not None and prof.num_ratings > 0
        assert prof.school is not None
        assert prof.school.name

    def test_professor_has_numeric_fields(self, client: RMPClient) -> None:
        prof = client.get_professor(PROFESSOR_ID)
        assert isinstance(prof.overall_rating, float)
        assert isinstance(prof.level_of_difficulty, float)
        assert isinstance(prof.num_ratings, int)

    def test_raises_error_for_invalid_id(self, client: RMPClient) -> None:
        with pytest.raises((ParsingError, RMPAPIError)):
            client.get_professor("999999999")


# ---------------------------------------------------------------------------
# get_school
# ---------------------------------------------------------------------------


class TestGetSchool:
    def test_returns_school_with_summary(self, client: RMPClient) -> None:
        school = client.get_school(SCHOOL_QUEENS)
        assert school.id == SCHOOL_QUEENS
        assert "Queen" in school.name
        assert school.location is not None
        assert school.overall_quality is not None
        assert school.num_ratings is not None and school.num_ratings > 0

    def test_has_category_ratings(self, client: RMPClient) -> None:
        school = client.get_school(SCHOOL_QUEENS)
        assert school.reputation is not None
        assert school.safety is not None
        assert school.happiness is not None
        assert school.facilities is not None
        assert school.social is not None
        assert school.food is not None
        assert school.internet is not None
        assert school.clubs is not None
        assert school.opportunities is not None
        assert school.location_rating is not None

    def test_raises_error_for_invalid_id(self, client: RMPClient) -> None:
        with pytest.raises((ParsingError, RMPAPIError)):
            client.get_school("999999999")


# ---------------------------------------------------------------------------
# get_compare_schools
# ---------------------------------------------------------------------------


class TestGetCompareSchools:
    def test_returns_both_schools(self, client: RMPClient) -> None:
        result = client.get_compare_schools(SCHOOL_QUEENS, SCHOOL_WESTERN)
        assert result.school_1.id == SCHOOL_QUEENS
        assert result.school_2.id == SCHOOL_WESTERN
        assert result.school_1.name != result.school_2.name
        assert result.school_1.num_ratings is not None
        assert result.school_2.num_ratings is not None


# ---------------------------------------------------------------------------
# get_professor_ratings_page (cached pagination)
# ---------------------------------------------------------------------------


class TestGetProfessorRatingsPage:
    def test_first_page(self, client: RMPClient) -> None:
        page = client.get_professor_ratings_page(PROFESSOR_ID, page_size=5)
        assert page.professor.id == PROFESSOR_ID
        assert page.professor.name
        assert len(page.ratings) > 0
        assert len(page.ratings) <= 5
        for r in page.ratings:
            assert r.date is not None
            assert isinstance(r.comment, str)

    def test_load_more_from_cache(self, client: RMPClient) -> None:
        p1 = client.get_professor_ratings_page(PROFESSOR_ID, page_size=3)
        assert p1.has_next_page is True
        assert p1.next_cursor is not None

        p2 = client.get_professor_ratings_page(
            PROFESSOR_ID, cursor=p1.next_cursor, page_size=3
        )
        assert len(p2.ratings) > 0
        p1_comments = {r.comment for r in p1.ratings}
        p2_comments = {r.comment for r in p2.ratings}
        assert p1_comments.isdisjoint(p2_comments), "Page 2 should not repeat page 1 ratings"

    def test_rating_fields_populated(self, client: RMPClient) -> None:
        page = client.get_professor_ratings_page(PROFESSOR_ID, page_size=5)
        for r in page.ratings:
            assert isinstance(r.date, date)
            assert r.quality is None or isinstance(r.quality, float)
            assert r.difficulty is None or isinstance(r.difficulty, float)
            assert isinstance(r.tags, list)

    def test_multiple_show_mores(self, client: RMPClient) -> None:
        all_comments: list[str] = []
        cursor = None
        pages_fetched = 0
        while pages_fetched < 4:
            page = client.get_professor_ratings_page(
                PROFESSOR_ID, cursor=cursor, page_size=5
            )
            all_comments.extend(r.comment for r in page.ratings)
            pages_fetched += 1
            if not page.has_next_page:
                break
            cursor = page.next_cursor

        assert len(all_comments) > 5, "Should have fetched more than one page worth"
        assert len(all_comments) == len(set(all_comments)), "No duplicate comments"


# ---------------------------------------------------------------------------
# get_school_ratings_page (cached pagination)
# ---------------------------------------------------------------------------


class TestGetSchoolRatingsPage:
    def test_first_page(self, client: RMPClient) -> None:
        page = client.get_school_ratings_page(SCHOOL_QUEENS, page_size=5)
        assert page.school.name
        assert len(page.ratings) > 0
        assert len(page.ratings) <= 5

    def test_has_category_ratings(self, client: RMPClient) -> None:
        page = client.get_school_ratings_page(SCHOOL_QUEENS, page_size=5)
        for r in page.ratings:
            assert isinstance(r.date, date)
            assert isinstance(r.comment, str)
            if r.category_ratings:
                assert isinstance(r.category_ratings, dict)
                assert len(r.category_ratings) > 0

    def test_load_more_from_cache(self, client: RMPClient) -> None:
        p1 = client.get_school_ratings_page(SCHOOL_QUEENS, page_size=3)
        if not p1.has_next_page:
            pytest.skip("School does not have enough ratings for multi-page test")

        p2 = client.get_school_ratings_page(
            SCHOOL_QUEENS, cursor=p1.next_cursor, page_size=3
        )
        assert len(p2.ratings) > 0

    def test_overall_score_computed(self, client: RMPClient) -> None:
        page = client.get_school_ratings_page(SCHOOL_QUEENS, page_size=5)
        for r in page.ratings:
            if r.category_ratings and len(r.category_ratings) > 0:
                assert r.overall is not None
                assert r.overall > 0


# ---------------------------------------------------------------------------
# iter_professor_ratings
# ---------------------------------------------------------------------------


class TestIterProfessorRatings:
    def test_yields_ratings(self, client: RMPClient) -> None:
        ratings = list(client.iter_professor_ratings(PROFESSOR_ID, page_size=5))
        assert len(ratings) > 0
        for r in ratings:
            assert isinstance(r.date, date)
            assert isinstance(r.comment, str)

    def test_since_date_stops_early(self, client: RMPClient) -> None:
        cutoff = date(2025, 1, 1)
        ratings = list(
            client.iter_professor_ratings(PROFESSOR_ID, page_size=10, since=cutoff)
        )
        for r in ratings:
            assert r.date > cutoff

    def test_collects_all_ratings(self, client: RMPClient) -> None:
        all_ratings = list(client.iter_professor_ratings(PROFESSOR_ID, page_size=20))
        assert len(all_ratings) > 0
        dates = [r.date for r in all_ratings]
        assert dates == sorted(dates, reverse=True) or len(dates) <= 1, \
            "Ratings should be in reverse chronological order"


# ---------------------------------------------------------------------------
# iter_school_ratings
# ---------------------------------------------------------------------------


class TestIterSchoolRatings:
    def test_yields_ratings(self, client: RMPClient) -> None:
        ratings = list(client.iter_school_ratings(SCHOOL_QUEENS, page_size=5))
        assert len(ratings) > 0
        for r in ratings:
            assert isinstance(r.date, date)
            assert isinstance(r.comment, str)

    def test_since_date_stops_early(self, client: RMPClient) -> None:
        cutoff = date(2025, 1, 1)
        ratings = list(
            client.iter_school_ratings(SCHOOL_QUEENS, page_size=10, since=cutoff)
        )
        for r in ratings:
            assert r.date > cutoff


# ---------------------------------------------------------------------------
# list_professors_for_school
# ---------------------------------------------------------------------------


class TestListProfessorsForSchool:
    def test_returns_professors(self, client: RMPClient) -> None:
        result = client.list_professors_for_school(int(SCHOOL_UW), page_size=5)
        assert len(result.professors) > 0
        for prof in result.professors:
            assert prof.id
            assert prof.name

    def test_cursor_pagination(self, client: RMPClient) -> None:
        p1 = client.list_professors_for_school(int(SCHOOL_UW), page_size=2)
        assert len(p1.professors) > 0
        assert p1.has_next_page is True

        p2 = client.list_professors_for_school(
            int(SCHOOL_UW), page_size=2, cursor=p1.next_cursor
        )
        assert len(p2.professors) > 0
        p1_ids = {p.id for p in p1.professors}
        p2_ids = {p.id for p in p2.professors}
        assert p1_ids.isdisjoint(p2_ids)


# ---------------------------------------------------------------------------
# iter_professors_for_school
# ---------------------------------------------------------------------------


class TestIterProfessorsForSchool:
    def test_yields_professors(self, client: RMPClient) -> None:
        profs = []
        for prof in client.iter_professors_for_school(int(SCHOOL_UW), page_size=5):
            profs.append(prof)
            if len(profs) >= 10:
                break
        assert len(profs) >= 5
        for prof in profs:
            assert prof.id
            assert prof.name

    def test_multi_page(self, client: RMPClient) -> None:
        profs = []
        for prof in client.iter_professors_for_school(int(SCHOOL_UW), page_size=2):
            profs.append(prof)
            if len(profs) >= 5:
                break
        assert len(profs) >= 3, "Should iterate across multiple pages"
        ids = [p.id for p in profs]
        assert len(ids) == len(set(ids)), "No duplicate professors"


# ---------------------------------------------------------------------------
# raw_query
# ---------------------------------------------------------------------------


class TestRawQuery:
    def test_sends_query_and_gets_response(self, client: RMPClient) -> None:
        from rmp_client.queries import GET_SCHOOL_QUERY
        import base64

        node_id = base64.b64encode(f"School-{SCHOOL_QUEENS}".encode()).decode()
        result = client.raw_query({
            "operationName": "GetSchoolQuery",
            "query": GET_SCHOOL_QUERY,
            "variables": {"id": node_id},
        })
        assert "data" in result
        assert result["data"]["node"] is not None
        assert "Queen" in result["data"]["node"]["name"]


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    def test_safe_to_call_multiple_times(self) -> None:
        c = RMPClient()
        c.close()
        c.close()
