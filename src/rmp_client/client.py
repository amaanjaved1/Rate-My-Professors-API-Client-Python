"""High-level client for the RateMyProfessors (RMP) GraphQL API.

All data is fetched via POST to https://www.ratemyprofessors.com/graphql.
Rate limiting, retries, and timeouts are handled by :class:`HttpClient`.

Call :meth:`RMPClient.close` when done to release resources.
"""

from __future__ import annotations

import base64
import warnings
from datetime import date
from typing import Any, Dict, Iterator, List, Mapping, Optional

from .config import RMPClientConfig
from .errors import ParsingError
from .http import HttpClient, HttpClientContext
from .models import (
    CompareSchoolsResult,
    Professor,
    ProfessorRatingsPage,
    ProfessorSearchResult,
    Rating,
    School,
    SchoolRating,
    SchoolRatingsPage,
    SchoolSearchResult,
)
from .queries import (
    RATINGS_LIST_QUERY,
    SCHOOL_RATINGS_LIST_QUERY,
    SCHOOL_SEARCH_RESULTS_QUERY,
    TEACHER_SEARCH_RESULTS_QUERY,
)


def _teacher_node_id(professor_id: str) -> str:
    """Relay global ID for a Teacher node: base64('Teacher-{legacyId}')."""
    return base64.b64encode(f"Teacher-{professor_id}".encode()).decode("ascii")


def _school_node_id(school_id: str) -> str:
    """Relay global ID for a School node: base64('School-{legacyId}')."""
    return base64.b64encode(f"School-{school_id}".encode()).decode("ascii")


def _format_location(record: Mapping[str, Any]) -> Optional[str]:
    """Build a location string from city/state/country fields."""
    parts = [record.get("city"), record.get("state"), record.get("country")]
    joined = ", ".join(p for p in parts if isinstance(p, str) and p.strip())
    return joined if joined else None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
        return f if f == f else None  # reject NaN
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coalesce(*values: Any) -> Any:
    """Return the first non-None value, or None if all are None."""
    return next((v for v in values if v is not None), None)


def _parse_date(date_str: Any) -> date:
    """Parse RMP date strings (e.g. '2026-03-03 21:20:35 +0000 UTC') to a date.

    Uses only the date part; invalid input warns and yields today's date.
    """
    if isinstance(date_str, str):
        part = date_str.split(" ")[0] if " " in date_str else date_str
        try:
            return date.fromisoformat(part)
        except ValueError:
            pass
    warnings.warn(f"Could not parse date {date_str!r}, using today", stacklevel=3)
    return date.today()


class RMPClient:
    """Main client for the RateMyProfessors GraphQL API.

    Use as a context manager or call :meth:`close` when finished.
    """

    def __init__(self, config: Optional[RMPClientConfig] = None) -> None:
        self._config = config or RMPClientConfig()
        self._http_ctx = HttpClientContext(self._config)
        self._http: Optional[HttpClient] = None

    def __enter__(self) -> "RMPClient":
        self._http = self._http_ctx.__enter__()
        return self

    def __exit__(self, *args: Any) -> None:
        self._http_ctx.__exit__(*args)
        self._http = None

    @property
    def _client(self) -> HttpClient:
        if self._http is None:
            self._http = HttpClient(self._config)
        return self._http

    def close(self) -> None:
        """Close the HTTP client. Safe to call multiple times."""
        if self._http is not None:
            self._http.close()
            self._http = None

    # ---- Low-level ---------------------------------------------------------------

    def raw_query(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Send a raw JSON/GraphQL payload to the RMP endpoint."""
        return self._client.post_json("", payload)

    # ---- School search -----------------------------------------------------------

    def search_schools(
        self,
        query: str,
        *,
        page_size: int = 20,
        cursor: Optional[str] = None,
    ) -> SchoolSearchResult:
        """Search schools by name (SchoolSearchResultsPageQuery)."""
        data = self.raw_query({
            "operationName": "SchoolSearchResultsPageQuery",
            "query": SCHOOL_SEARCH_RESULTS_QUERY,
            "variables": {
                "query": {"text": query},
                "count": page_size,
                "cursor": cursor or "",
            },
        })

        search = (data.get("data") or {}).get("search")
        conn = search.get("schools") if isinstance(search, dict) else None
        if not conn:
            return SchoolSearchResult(
                schools=[],
                total=None,
                page_size=0,
                has_next_page=False,
                next_cursor=None,
            )

        edges = conn.get("edges") or []
        page_info = conn.get("pageInfo") or {}
        schools: List[School] = []
        for edge in edges:
            node = edge.get("node") if isinstance(edge, dict) else None
            if node:
                schools.append(self._parse_school_node(node))

        return SchoolSearchResult(
            schools=schools,
            total=_safe_int(conn.get("resultCount")),
            page_size=len(schools),
            has_next_page=bool(page_info.get("hasNextPage")),
            next_cursor=(
                str(page_info["endCursor"])
                if page_info.get("endCursor") is not None
                else None
            ),
        )

    # ---- Professor search / listing ----------------------------------------------

    def search_professors(
        self,
        query: str,
        *,
        school_id: Optional[str] = None,
        page_size: int = 20,
        cursor: Optional[str] = None,
    ) -> ProfessorSearchResult:
        """Search professors by name (TeacherSearchResultsPageQuery)."""
        query_var: Dict[str, Any] = {"text": query}
        if school_id is not None:
            query_var["schoolID"] = _school_node_id(school_id)

        data = self.raw_query({
            "operationName": "TeacherSearchResultsPageQuery",
            "query": TEACHER_SEARCH_RESULTS_QUERY,
            "variables": {
                "query": query_var,
                "count": page_size,
                "cursor": cursor or "",
            },
        })

        search = (data.get("data") or {}).get("search")
        conn = search.get("teachers") if isinstance(search, dict) else None
        if not conn:
            return ProfessorSearchResult(
                professors=[],
                total=None,
                page_size=0,
                has_next_page=False,
                next_cursor=None,
            )

        edges = conn.get("edges") or []
        page_info = conn.get("pageInfo") or {}
        professors: List[Professor] = []
        for edge in edges:
            node = edge.get("node") if isinstance(edge, dict) else None
            if node:
                professors.append(self._parse_professor_node(node))

        return ProfessorSearchResult(
            professors=professors,
            total=_safe_int(conn.get("resultCount")),
            page_size=len(professors),
            has_next_page=bool(page_info.get("hasNextPage")),
            next_cursor=(
                str(page_info["endCursor"])
                if page_info.get("endCursor") is not None
                else None
            ),
        )

    def list_professors_for_school(
        self,
        school_id: int,
        *,
        query: Optional[str] = None,
        page_size: int = 20,
        cursor: Optional[str] = None,
    ) -> ProfessorSearchResult:
        """List professors at a school. Wrapper around :meth:`search_professors`."""
        return self.search_professors(
            query=query if query else " ",
            school_id=str(school_id),
            page_size=page_size,
            cursor=cursor,
        )

    def iter_professors_for_school(
        self,
        school_id: int,
        *,
        query: Optional[str] = None,
        page_size: int = 20,
    ) -> Iterator[Professor]:
        """Iterate all professors at a school, handling cursor pagination."""
        cursor: Optional[str] = None
        while True:
            result = self.list_professors_for_school(
                school_id=school_id,
                query=query,
                page_size=page_size,
                cursor=cursor,
            )
            for prof in result.professors:
                yield prof
            if (
                not result.has_next_page
                or not result.next_cursor
                or not result.professors
            ):
                break
            cursor = result.next_cursor

    # ---- Professor details + ratings ---------------------------------------------

    def get_professor(self, professor_id: str) -> Professor:
        """Fetch a single professor by legacy numeric ID."""
        page = self._fetch_professor_ratings_page(professor_id, first=1)
        return page.professor

    def get_professor_ratings_page(
        self,
        professor_id: str,
        *,
        cursor: Optional[str] = None,
        page_size: int = 20,
        course_filter: Optional[str] = None,
    ) -> ProfessorRatingsPage:
        """Fetch one page of ratings for a professor."""
        return self._fetch_professor_ratings_page(
            professor_id,
            after=cursor,
            first=page_size,
            course_filter=course_filter,
        )

    def iter_professor_ratings(
        self,
        professor_id: str,
        *,
        page_size: int = 20,
        since: Optional[date] = None,
        course_filter: Optional[str] = None,
    ) -> Iterator[Rating]:
        """Iterate all ratings for a professor.

        ``since`` stops iteration early; assumes the API returns ratings
        newest-first, which is the observed behaviour.
        """
        cursor: Optional[str] = None
        while True:
            page = self.get_professor_ratings_page(
                professor_id,
                cursor=cursor,
                page_size=page_size,
                course_filter=course_filter,
            )
            for rating in page.ratings:
                if since is not None and rating.date <= since:
                    return
                yield rating
            if not page.has_next_page or not page.next_cursor:
                return
            cursor = page.next_cursor

    # ---- School details + ratings ------------------------------------------------

    def get_school(self, school_id: str) -> School:
        """Fetch a single school by legacy numeric ID."""
        page = self._fetch_school_ratings_page(school_id, first=1)
        return page.school

    def get_compare_schools(
        self, school_id_1: str, school_id_2: str
    ) -> CompareSchoolsResult:
        """Fetch two schools and return them as a pair."""
        school_1 = self.get_school(school_id_1)
        school_2 = self.get_school(school_id_2)
        return CompareSchoolsResult(school_1=school_1, school_2=school_2)

    def get_school_ratings_page(
        self,
        school_id: str,
        *,
        cursor: Optional[str] = None,
        page_size: int = 20,
    ) -> SchoolRatingsPage:
        """Fetch one page of school ratings."""
        return self._fetch_school_ratings_page(school_id, after=cursor, first=page_size)

    def iter_school_ratings(
        self,
        school_id: str,
        *,
        page_size: int = 20,
        since: Optional[date] = None,
    ) -> Iterator[SchoolRating]:
        """Iterate all ratings for a school.

        ``since`` stops iteration early; assumes the API returns ratings
        newest-first, which is the observed behaviour.
        """
        cursor: Optional[str] = None
        while True:
            page = self.get_school_ratings_page(
                school_id, cursor=cursor, page_size=page_size
            )
            for rating in page.ratings:
                if since is not None and rating.date <= since:
                    return
                yield rating
            if not page.has_next_page or not page.next_cursor:
                return
            cursor = page.next_cursor

    # ---- Private GraphQL page fetchers -------------------------------------------

    def _fetch_professor_ratings_page(
        self,
        professor_id: str,
        *,
        after: Optional[str] = None,
        first: int = 20,
        course_filter: Optional[str] = None,
    ) -> ProfessorRatingsPage:
        node_id = _teacher_node_id(professor_id)
        variables: Dict[str, Any] = {
            "count": first,
            "id": node_id,
            "courseFilter": course_filter,
        }
        if after is not None:
            variables["cursor"] = after

        data = self.raw_query({
            "operationName": "RatingsListQuery",
            "query": RATINGS_LIST_QUERY,
            "variables": variables,
        })

        node = (data.get("data") or {}).get("node")
        if not node:
            raise ParsingError(
                "GraphQL response missing data.node (teacher not found or invalid id)"
            )

        school_obj = node.get("school")
        school: Optional[School] = None
        if isinstance(school_obj, dict):
            school = self._parse_school_node(school_obj)

        name = " ".join(
            filter(None, [node.get("firstName"), node.get("lastName")])
        ).strip()

        professor = Professor(
            id=str(node.get("legacyId") or node.get("id") or professor_id),
            name=name or "Unknown",
            department=node.get("department"),
            school=school,
            overall_rating=_safe_float(_coalesce(node.get("avgRating"), node.get("overallRating"))),
            num_ratings=_safe_int(node.get("numRatings")),
            percent_take_again=_safe_float(_coalesce(node.get("wouldTakeAgainPercent"), node.get("percentTakeAgain"))),
            level_of_difficulty=_safe_float(_coalesce(node.get("avgDifficulty"), node.get("levelOfDifficulty"))),
        )

        ratings_conn = node.get("ratings") or {}
        edges = ratings_conn.get("edges") or []
        page_info = ratings_conn.get("pageInfo") or {}
        ratings: List[Rating] = []
        for edge in edges:
            r = edge.get("node") if isinstance(edge, dict) else None
            if isinstance(r, dict):
                ratings.append(self._parse_rating_node(r))

        return ProfessorRatingsPage(
            professor=professor,
            ratings=ratings,
            has_next_page=bool(page_info.get("hasNextPage")),
            next_cursor=(
                str(page_info["endCursor"])
                if page_info.get("endCursor") is not None
                else None
            ),
        )

    def _fetch_school_ratings_page(
        self,
        school_id: str,
        *,
        after: Optional[str] = None,
        first: int = 20,
    ) -> SchoolRatingsPage:
        node_id = _school_node_id(school_id)
        variables: Dict[str, Any] = {"count": first, "id": node_id}
        if after is not None:
            variables["cursor"] = after

        data = self.raw_query({
            "operationName": "SchoolRatingsListQuery",
            "query": SCHOOL_RATINGS_LIST_QUERY,
            "variables": variables,
        })

        node = (data.get("data") or {}).get("node")
        if not node:
            raise ParsingError(
                "GraphQL response missing data.node (school not found or invalid id)"
            )

        school = self._parse_school_node(node)

        ratings_conn = node.get("ratings") or {}
        edges = ratings_conn.get("edges") or []
        page_info = ratings_conn.get("pageInfo") or {}
        ratings: List[SchoolRating] = []
        for edge in edges:
            r = edge.get("node") if isinstance(edge, dict) else None
            if isinstance(r, dict):
                ratings.append(self._parse_school_rating_node(r))

        return SchoolRatingsPage(
            school=school,
            ratings=ratings,
            has_next_page=bool(page_info.get("hasNextPage")),
            next_cursor=(
                str(page_info["endCursor"])
                if page_info.get("endCursor") is not None
                else None
            ),
        )

    # ---- Internal parsers --------------------------------------------------------

    def _parse_professor_node(self, node: Mapping[str, Any]) -> Professor:
        first_name = node.get("firstName")
        last_name = node.get("lastName")
        name = (
            node.get("name")
            or " ".join(filter(None, [first_name, last_name])).strip()
            or "Unknown"
        )

        school_obj = node.get("school")
        school: Optional[School] = None
        if isinstance(school_obj, dict):
            school = self._parse_school_node(school_obj)

        return Professor(
            id=str(node.get("legacyId") or node.get("id") or ""),
            name=name,
            department=node.get("department"),
            school=school,
            overall_rating=_safe_float(
                _coalesce(node.get("avgRating"), node.get("overallRating"))
            ),
            num_ratings=_safe_int(node.get("numRatings")),
            percent_take_again=_safe_float(
                _coalesce(node.get("wouldTakeAgainPercent"), node.get("percentTakeAgain"))
            ),
            level_of_difficulty=_safe_float(
                _coalesce(node.get("avgDifficulty"), node.get("levelOfDifficulty"))
            ),
            tags=[],
            rating_distribution=None,
        )

    def _parse_rating_node(self, record: Mapping[str, Any]) -> Rating:
        tags: List[str] = []
        rating_tags = record.get("ratingTags")
        if isinstance(rating_tags, str):
            tags = [t.strip() for t in rating_tags.split("--") if t.strip()]

        details: Optional[Dict[str, Any]] = None
        for api_key, detail_key in (
            ("isForCredit", "for_credit"),
            ("attendanceMandatory", "attendance"),
            ("grade", "grade"),
            ("textbookUse", "textbook"),
        ):
            val = record.get(api_key)
            if val is not None:
                if details is None:
                    details = {}
                details[detail_key] = val

        return Rating(
            date=_parse_date(record.get("date")),
            comment=str(record.get("comment") or ""),
            quality=_safe_float(
                _coalesce(record.get("clarityRating"), record.get("helpfulRating"))
            ),
            difficulty=_safe_float(record.get("difficultyRating")),
            tags=tags,
            course_raw=record.get("class") or None,
            details=details,
            thumbs_up=_safe_int(record.get("thumbsUpTotal")),
            thumbs_down=_safe_int(record.get("thumbsDownTotal")),
        )

    def _parse_school_node(self, node: Mapping[str, Any]) -> School:
        summary = node.get("summary") if isinstance(node.get("summary"), dict) else None
        return School(
            id=str(_coalesce(node.get("legacyId"), node.get("id")) or ""),
            name=str(node.get("name") or ""),
            location=_format_location(node),
            overall_quality=_safe_float(_coalesce(node.get("avgRatingRounded"), node.get("avgRating"))),
            num_ratings=_safe_int(node.get("numRatings")),
            reputation=_safe_float(_coalesce((summary or {}).get("schoolReputation"), node.get("reputation"))),
            safety=_safe_float(_coalesce((summary or {}).get("schoolSafety"), node.get("safety"))),
            happiness=_safe_float(_coalesce((summary or {}).get("schoolSatisfaction"), node.get("happiness"))),
            facilities=_safe_float(_coalesce((summary or {}).get("campusCondition"), node.get("facilities"))),
            social=_safe_float(_coalesce((summary or {}).get("socialActivities"), node.get("social"))),
            location_rating=_safe_float(_coalesce((summary or {}).get("campusLocation"), node.get("location_rating"))),
            clubs=_safe_float(_coalesce((summary or {}).get("clubAndEventActivities"), node.get("clubs"))),
            opportunities=_safe_float(_coalesce((summary or {}).get("careerOpportunities"), node.get("opportunities"))),
            internet=_safe_float(_coalesce((summary or {}).get("internetSpeed"), node.get("internet"))),
            food=_safe_float(_coalesce((summary or {}).get("foodQuality"), node.get("food"))),
        )

    def _parse_school_rating_node(self, record: Mapping[str, Any]) -> SchoolRating:
        rmp_to_category = (
            ("reputationRating", "reputation"),
            ("locationRating", "location"),
            ("opportunitiesRating", "opportunities"),
            ("facilitiesRating", "facilities"),
            ("internetRating", "internet"),
            ("foodRating", "food"),
            ("clubsRating", "clubs"),
            ("socialRating", "social"),
            ("happinessRating", "happiness"),
            ("safetyRating", "safety"),
        )

        category_ratings: Optional[Dict[str, float]] = None
        for rmp_key, cat_key in rmp_to_category:
            f = _safe_float(record.get(rmp_key))
            if f is not None:
                if category_ratings is None:
                    category_ratings = {}
                category_ratings[cat_key] = f

        overall: Optional[float] = None
        if category_ratings:
            vals = list(category_ratings.values())
            overall = sum(vals) / len(vals)

        return SchoolRating(
            date=_parse_date(record.get("date")),
            comment=str(record.get("comment") or ""),
            overall=overall,
            category_ratings=category_ratings,
            thumbs_up=_safe_int(record.get("thumbsUpTotal")),
            thumbs_down=_safe_int(record.get("thumbsDownTotal")),
        )
