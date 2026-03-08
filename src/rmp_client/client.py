from __future__ import annotations

import base64
import json
from datetime import date
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional
from urllib.parse import quote

from .config import RMPClientConfig
from .errors import ParsingError
from .http import HttpClient, HttpClientContext
from .models import (
    CompareSchoolsResult,
    Professor,
    ProfessorRatingsPage,
    ProfessorSearchResult,
    Rating,
    RatingDistributionBucket,
    School,
    SchoolRating,
    SchoolRatingsPage,
    SchoolSearchResult,
)
from .relay_store import (
    extract_relay_store,
    get_all_rating_records,
    get_all_school_rating_records,
    get_professor_node,
    get_professor_ratings_connection_page_info,
    get_ratings_from_store,
    get_school_node,
    get_school_ratings_connection_page_info,
    get_school_ratings_from_store,
    get_school_search_connection,
    get_school_search_page_info,
    get_school_search_result_count,
    get_teacher_search_connection,
    get_teacher_search_page_info,
    get_teacher_search_result_count,
    _edges_to_school_records,
    _edges_to_teacher_records,
    _is_record_ref,
    _resolve_ref,
    _resolve_refs,
)

# GraphQL query for teacher ratings with cursor-based pagination (RMP uses Relay).
# Node id must be base64("Teacher-{legacyId}").
TEACHER_RATINGS_QUERY = """
query TeacherRatings($id: ID!, $first: Int!, $after: String) {
  node(id: $id) {
    ... on Teacher {
      id
      legacyId
      firstName
      lastName
      department
      avgRating
      avgDifficulty
      numRatings
      wouldTakeAgainPercent
      school {
        id
        name
        city
        state
      }
      ratings(first: $first, after: $after) {
        edges {
          node {
            comment
            ratingTags
            clarityRating
            difficultyRating
            date
            grade
            helpfulRating
            thumbsUpTotal
            thumbsDownTotal
            class
            attendanceMandatory
            textbookUse
            isForCredit
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""


def _teacher_node_id(professor_id: str) -> str:
    """Relay global id for Teacher node: base64('Teacher-{legacyId}')."""
    raw = f"Teacher-{professor_id}"
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def _school_node_id(school_id: str) -> str:
    """Relay global id for School node: base64('School-{legacyId}')."""
    raw = f"School-{school_id}"
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


# GraphQL query for school ratings with cursor-based pagination.
SCHOOL_RATINGS_QUERY = """
query SchoolRatings($id: ID!, $first: Int!, $after: String) {
  node(id: $id) {
    ... on School {
      id
      legacyId
      name
      city
      state
      avgRatingRounded
      numRatings
      ratings(first: $first, after: $after) {
        edges {
          node {
            comment
            date
            reputationRating
            locationRating
            opportunitiesRating
            facilitiesRating
            internetRating
            foodRating
            clubsRating
            socialRating
            happinessRating
            safetyRating
            thumbsUpTotal
            thumbsDownTotal
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""


def _format_location(record: Mapping[str, Any]) -> Optional[str]:
    """Build the single location string for a record.

    Uses record['location'] if present; otherwise joins city, state, country
    from the API into one string.
    """
    loc = record.get("location")
    if isinstance(loc, str) and loc.strip():
        return loc.strip()
    parts = [
        record.get("city"),
        record.get("state"),
        record.get("country"),
    ]
    joined = ", ".join(p for p in parts if isinstance(p, str) and p.strip())
    return joined if joined else None


def _school_record_to_location_dict(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a minimal school dict with id, name, and location."""
    return {
        "id": record.get("id") or record.get("__id"),
        "name": record.get("name") or "",
        "location": _format_location(record),
    }


def _build_rating_distribution(
    raw: Any,
) -> Optional[Dict[int, RatingDistributionBucket]]:
    """Convert raw counts (dict 1-5 or r1..r5 -> count, or list) to dict with count + percentage."""
    if raw is None:
        return None
    counts: Dict[int, int] = {}
    if isinstance(raw, dict):
        # RMP uses r1, r2, r3, r4, r5 for rating distribution
        if any(raw.get(f"r{i}") is not None for i in range(1, 6)):
            for i in range(1, 6):
                v = raw.get(f"r{i}")
                counts[i] = int(v) if v is not None else 0
        else:
            for k, v in raw.items():
                level = int(k) if isinstance(k, int) else (int(k) if isinstance(k, str) and k.isdigit() else None)
                if level is not None and 1 <= level <= 5:
                    counts[level] = int(v) if v is not None else 0
    elif isinstance(raw, list) and len(raw) >= 5:
        for i, v in enumerate(raw[:5], start=1):
            counts[i] = int(v) if v is not None else 0
    if not counts:
        return None
    total = sum(counts.values())
    if total <= 0:
        return None
    return {
        level: RatingDistributionBucket(
            count=count,
            percentage=round(100.0 * count / total, 2),
        )
        for level, count in sorted(counts.items())
    }


class RMPClient:
    """High-level client for RateMyProfessors.

    This is intentionally small for now; we will extend as we learn more about
    the underlying API shapes.
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
            # Lazily create a client if not used as context manager
            self._http = HttpClient(self._config)
        return self._http

    # ---- Low-level escape hatch -------------------------------------------------

    def raw_query(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Send a raw JSON/GraphQL-style payload to the RMP backend."""
        return self._client.post_json("", payload)

    # ---- School search ----------------------------------------------------------

    def _search_schools_page_url(self, query: str) -> str:
        """URL for school search page: /search/schools?q=..."""
        base = self._config.search_schools_page_url.rstrip("/")
        return f"{base}?q={quote(query, safe='')}"

    def _fetch_relay_store_for_search_schools(self, query: str) -> Dict[str, Any]:
        """GET school search page HTML and return parsed __RELAY_STORE__."""
        url = self._search_schools_page_url(query)
        html = self._client.get_html(url)
        try:
            return extract_relay_store(html)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ParsingError(f"Failed to extract __RELAY_STORE__ from school search page: {exc}") from exc

    def search_schools(
        self,
        query: str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> SchoolSearchResult:
        """Search schools by name.

        Loads the search page HTML (/search/schools?q=...) and parses
        __RELAY_STORE__ for the first page of results. total and has_next_page
        come from the relay; page_size is the number of results on that page.
        """
        store = self._fetch_relay_store_for_search_schools(query)
        conn = get_school_search_connection(store)
        if conn is None:
            return SchoolSearchResult(
                schools=[],
                total=None,
                page=page,
                page_size=page_size,
                has_next_page=False,
                next_cursor=None,
            )
        school_records = _edges_to_school_records(store, conn.get("edges"))
        schools: List[School] = []
        for rec in school_records:
            node = self._relay_school_to_node(store, rec)
            schools.append(self._parse_school_node(node))
        total = get_school_search_result_count(conn)
        page_info = get_school_search_page_info(store, conn)
        has_next = bool(page_info.get("hasNextPage", False)) if page_info else False
        next_cursor = page_info.get("endCursor") if page_info else None
        return SchoolSearchResult(
            schools=schools,
            total=total,
            page=page,
            page_size=len(schools),
            has_next_page=has_next,
            next_cursor=next_cursor,
        )

    # ---- Professor search / listing --------------------------------------------

    def _search_professors_page_url(self, query: str) -> str:
        """URL for professor search page: /search/professors/?q=..."""
        base = self._config.search_professors_page_url.rstrip("/")
        return f"{base}?q={quote(query, safe='')}"

    def _fetch_relay_store_for_search_professors(self, query: str) -> Dict[str, Any]:
        """GET professor search page HTML and return parsed __RELAY_STORE__."""
        url = self._search_professors_page_url(query)
        html = self._client.get_html(url)
        try:
            return extract_relay_store(html)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ParsingError(f"Failed to extract __RELAY_STORE__ from search page: {exc}") from exc

    def search_professors(
        self,
        query: str,
        *,
        school_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ProfessorSearchResult:
        """Search professors by name (and optional school filter).

        Loads the search page HTML (/search/professors/?q=...) and parses
        __RELAY_STORE__ for the first page of results. total and has_next_page
        come from the relay; page_size is the number of results on that page.
        For listing all professors at a school, use list_professors_for_school
        or iter_professors_for_school.
        """
        store = self._fetch_relay_store_for_search_professors(query)
        conn = get_teacher_search_connection(store)
        if conn is None:
            return ProfessorSearchResult(
                professors=[],
                total=None,
                page=page,
                page_size=page_size,
                has_next_page=False,
                next_cursor=None,
            )
        teacher_records = _edges_to_teacher_records(store, conn.get("edges"))
        professors: List[Professor] = []
        for rec in teacher_records:
            node = self._relay_professor_to_node(store, rec)
            professors.append(self._parse_professor_node(node))
        total = get_teacher_search_result_count(conn)
        page_info = get_teacher_search_page_info(store, conn)
        has_next = bool(page_info.get("hasNextPage", False)) if page_info else False
        next_cursor = page_info.get("endCursor") if page_info else None
        return ProfessorSearchResult(
            professors=professors,
            total=total,
            page=page,
            page_size=len(professors),
            has_next_page=has_next,
            next_cursor=next_cursor,
        )

    def list_professors_for_school(
        self,
        school_id: int,
        *,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ProfessorSearchResult:
        """Convenience wrapper to list professors for a given school."""
        return self.search_professors(
            query=query or "*",
            school_id=str(school_id),
            page=page,
            page_size=page_size,
        )

    def iter_professors_for_school(
        self,
        school_id: int,
        *,
        query: Optional[str] = None,
        page_size: int = 20,
    ) -> Iterator[Professor]:
        """Iterate all professors for a school, handling pagination for you."""
        page = 1
        while True:
            result = self.list_professors_for_school(
                school_id=school_id,
                query=query,
                page=page,
                page_size=page_size,
            )
            if not result.professors:
                break
            for prof in result.professors:
                yield prof
            if not result.has_next_page:
                break
            page += 1

    # ---- Professor details + ratings -------------------------------------------

    def _professor_page_url(self, professor_id: str) -> str:
        base = self._config.professors_page_url.rstrip("/")
        return f"{base}/{professor_id}"

    def _fetch_relay_store_for_professor(self, professor_id: str) -> Dict[str, Any]:
        """GET professor page HTML and return parsed __RELAY_STORE__."""
        url = self._professor_page_url(professor_id)
        html = self._client.get_html(url)
        try:
            return extract_relay_store(html)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ParsingError(f"Failed to extract __RELAY_STORE__ from professor page: {exc}") from exc

    def _relay_professor_to_node(self, store: Dict[str, Any], record: Mapping[str, Any]) -> Dict[str, Any]:
        """Convert a Relay Professor/Teacher record to the shape _parse_professor_node expects."""
        # RMP professor page uses avgRating, avgDifficulty, wouldTakeAgainPercent
        node: Dict[str, Any] = {
            "id": record.get("id") or record.get("__id") or record.get("legacyId"),
            "name": record.get("name") or " ".join(filter(None, [record.get("firstName"), record.get("lastName")])),
            "department": record.get("department"),
            "url": record.get("url"),
            "overallRating": record.get("avgRating") or record.get("overallRating"),
            "numRatings": record.get("numRatings"),
            "percentTakeAgain": record.get("wouldTakeAgainPercent") or record.get("percentTakeAgain"),
            "levelOfDifficulty": record.get("avgDifficulty") or record.get("levelOfDifficulty"),
            "tags": record.get("tags") or [],
        }
        school_val = record.get("school")
        if school_val is not None and isinstance(school_val, dict) and "__ref" in school_val:
            school_record = _resolve_ref(store, school_val)
            if school_record and isinstance(school_record, dict):
                node["school"] = _school_record_to_location_dict(school_record)
        elif isinstance(school_val, dict):
            node["school"] = _school_record_to_location_dict(school_val)
        # Rating distribution: RMP stores as __ref to record with r1..r5
        dist_raw = record.get("ratingsDistribution") or record.get("ratingDistribution")
        if _is_record_ref(dist_raw):
            dist_record = _resolve_ref(store, dist_raw)
            node["rating_distribution"] = dist_record if isinstance(dist_record, dict) else dist_raw
        else:
            node["rating_distribution"] = dist_raw
        # Tags: RMP uses teacherRatingTags as {"__refs": ["id1", ...]}; each ref is TeacherRatingTags with tagName
        tags_refs = record.get("teacherRatingTags")
        if isinstance(tags_refs, dict) and "__refs" in tags_refs:
            ref_ids = tags_refs.get("__refs") or []
            tag_records = _resolve_refs(store, ref_ids)
            node["tags"] = [str(r.get("tagName", "")) for r in tag_records if r.get("tagName")]
        elif not node["tags"]:
            node["tags"] = record.get("tags") or []
        return node

    def _relay_rating_to_node(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        """Convert a Relay Rating record to the shape _parse_rating_node expects."""
        # RMP uses clarityRating (quality), difficultyRating, class (course), helpfulRating, thumbsUpTotal/thumbsDownTotal
        out: Dict[str, Any] = {
            "date": record.get("date"),
            "comment": record.get("comment") or "",
            "quality": record.get("clarityRating") or record.get("quality"),
            "difficulty": record.get("difficultyRating") or record.get("difficulty"),
            "tags": record.get("tags") or [],
            "course": record.get("class") or record.get("course") or record.get("courseName"),
        }
        # ratingTags is a single string "Tag1--Tag2--Tag3"
        if isinstance(record.get("ratingTags"), str):
            out["tags"] = [t.strip() for t in record["ratingTags"].split("--") if t.strip()]
        # Details: RMP uses attendanceMandatory, textbookUse, isForCredit, grade
        out["for_credit"] = record.get("isForCredit") if "isForCredit" in record else record.get("for_credit") or record.get("forCredit")
        out["attendance"] = record.get("attendanceMandatory") or record.get("attendance")
        out["grade"] = record.get("grade")
        out["textbook"] = record.get("textbookUse") if "textbookUse" in record else record.get("textbook")
        out["helpful"] = record.get("helpfulRating") or record.get("helpful")
        out["thumbsUp"] = record.get("thumbsUpTotal") or record.get("thumbsUp")
        out["thumbsDown"] = record.get("thumbsDownTotal") or record.get("thumbsDown")
        return out

    def get_professor(self, professor_id: str) -> Professor:
        """Fetch detailed information about a single professor.

        Data is loaded from the professor page HTML (server-side rendered);
        no separate API call is made.
        """
        store = self._fetch_relay_store_for_professor(professor_id)
        record = get_professor_node(store, professor_id)
        if record is None:
            raise ParsingError(f"Professor record not found in __RELAY_STORE__ for id={professor_id!r}")
        node = self._relay_professor_to_node(store, record)
        return self._parse_professor_node(node)

    def _fetch_professor_ratings_via_graphql(
        self,
        professor_id: str,
        *,
        after: Optional[str] = None,
        first: int = 20,
    ) -> ProfessorRatingsPage:
        """Fetch a page of professor ratings from the GraphQL API (for cursor-based next pages)."""
        node_id = _teacher_node_id(professor_id)
        variables: Dict[str, Any] = {"id": node_id, "first": first}
        if after is not None:
            variables["after"] = after
        payload: Dict[str, Any] = {
            "query": TEACHER_RATINGS_QUERY,
            "variables": variables,
        }
        data = self.raw_query(payload)
        node = (data.get("data") or {}).get("node")
        if not node:
            raise ParsingError("GraphQL response missing data.node (teacher not found or invalid id)")
        # Build Professor from Teacher fragment
        school_obj = node.get("school")
        school: Optional[School] = None
        if isinstance(school_obj, dict):
            loc = _format_location(school_obj)
            school = School(
                id=str(school_obj.get("id") or ""),
                name=str(school_obj.get("name") or ""),
                location=loc,
            )
        name = " ".join(filter(None, [node.get("firstName"), node.get("lastName")])).strip()
        professor = Professor(
            id=str(node.get("legacyId") or node.get("id") or professor_id),
            name=name or "Unknown",
            department=node.get("department"),
            school=school,
            overall_rating=node.get("avgRating"),
            num_ratings=node.get("numRatings"),
            percent_take_again=node.get("wouldTakeAgainPercent"),
            level_of_difficulty=node.get("avgDifficulty"),
        )
        ratings_conn = node.get("ratings") or {}
        edges = ratings_conn.get("edges") or []
        page_info = ratings_conn.get("pageInfo") or {}
        ratings_models: List[Rating] = []
        for edge in edges:
            r = edge.get("node") if isinstance(edge, dict) else None
            if not isinstance(r, dict):
                continue
            norm = self._relay_rating_to_node(r)
            ratings_models.append(self._parse_rating_node(norm))
        has_next = bool(page_info.get("hasNextPage", False))
        next_cursor = page_info.get("endCursor") if page_info else None
        return ProfessorRatingsPage(
            professor=professor,
            ratings=ratings_models,
            has_next_page=has_next,
            next_cursor=next_cursor,
        )

    def get_professor_ratings_page(
        self,
        professor_id: str,
        *,
        cursor: Optional[str] = None,
        page_size: int = 20,
    ) -> ProfessorRatingsPage:
        """Fetch a single page of ratings/comments for a professor.

        First page is loaded from the professor page HTML. Subsequent pages are
        fetched via the GraphQL API using the returned next_cursor, so you can
        iterate all ratings with iter_professor_ratings or by calling this
        repeatedly with cursor=page.next_cursor.
        """
        # Relay cursor (from pageInfo.endCursor): use GraphQL for next page
        if cursor is not None and not cursor.isdigit():
            return self._fetch_professor_ratings_via_graphql(
                professor_id, after=cursor, first=page_size
            )
        # First page or legacy numeric offset: from HTML
        store = self._fetch_relay_store_for_professor(professor_id)
        record = get_professor_node(store, professor_id)
        if record is None:
            raise ParsingError(f"Professor record not found in __RELAY_STORE__ for id={professor_id!r}")

        professor = self._parse_professor_node(self._relay_professor_to_node(store, record))
        rating_records = get_ratings_from_store(store, record)
        if not rating_records:
            rating_records = get_all_rating_records(store)

        ratings_models: List[Rating] = []
        for r in rating_records:
            node = self._relay_rating_to_node(r)
            ratings_models.append(self._parse_rating_node(node))

        page_info = get_professor_ratings_connection_page_info(store, record)
        if cursor is not None and cursor.isdigit():
            # Legacy: in-memory offset pagination over the single HTML batch
            start = max(0, int(cursor))
            page_slice = ratings_models[start : start + page_size]
            has_next = (start + page_size) < len(ratings_models)
            next_cursor = str(start + page_size) if has_next else None
        else:
            # First page: use Relay pageInfo when available so caller can fetch more via GraphQL; else in-memory
            page_slice = ratings_models[:page_size]
            if page_info and page_info.get("hasNextPage") and page_info.get("endCursor"):
                has_next = True
                next_cursor = page_info.get("endCursor")
            else:
                has_next = len(ratings_models) > page_size
                next_cursor = str(page_size) if has_next else None

        return ProfessorRatingsPage(
            professor=professor,
            ratings=page_slice,
            has_next_page=has_next,
            next_cursor=next_cursor,
        )

    def iter_professor_ratings(
        self,
        professor_id: str,
        *,
        page_size: int = 20,
        since: Optional[date] = None,
    ) -> Iterator[Rating]:
        """Iterate ratings for a professor, optionally stopping once `since` is reached."""
        cursor: Optional[str] = None
        while True:
            page = self.get_professor_ratings_page(
                professor_id=professor_id,
                cursor=cursor,
                page_size=page_size,
            )
            for rating in page.ratings:
                if since is not None and rating.date <= since:
                    return
                yield rating
            if not page.has_next_page or not page.next_cursor:
                return
            cursor = page.next_cursor

    # ---- School details + ratings -----------------------------------------------

    def _school_page_url(self, school_id: str) -> str:
        base = self._config.schools_page_url.rstrip("/")
        return f"{base}/{school_id}"

    def _compare_school_page_url(self, school_id: str) -> str:
        base = self._config.compare_schools_page_url.rstrip("/")
        return f"{base}/{school_id}"

    def _compare_schools_page_url(self, school_id_1: str, school_id_2: str) -> str:
        """URL for compare page: /compare/schools/id1/id2."""
        base = self._config.compare_schools_page_url.rstrip("/")
        return f"{base}/{school_id_1}/{school_id_2}"

    def _fetch_relay_store_for_school(self, school_id: str, *, use_compare_url: bool = False) -> Dict[str, Any]:
        """GET school page (or compare page) HTML and return parsed __RELAY_STORE__."""
        url = self._compare_school_page_url(school_id) if use_compare_url else self._school_page_url(school_id)
        html = self._client.get_html(url)
        try:
            return extract_relay_store(html)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ParsingError(f"Failed to extract __RELAY_STORE__ from school page: {exc}") from exc

    def _fetch_relay_store_for_compare_schools(
        self, school_id_1: str, school_id_2: str
    ) -> Dict[str, Any]:
        """GET compare schools page HTML and return parsed __RELAY_STORE__."""
        url = self._compare_schools_page_url(school_id_1, school_id_2)
        html = self._client.get_html(url)
        try:
            return extract_relay_store(html)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ParsingError(f"Failed to extract __RELAY_STORE__ from compare schools page: {exc}") from exc

    def _relay_school_to_node(self, store: Dict[str, Any], record: Mapping[str, Any]) -> Dict[str, Any]:
        """Convert a Relay School record to the shape _parse_school_node expects.

        RMP school page: overall from avgRatingRounded; category bars from summary __ref (SchoolSummary).
        """
        node: Dict[str, Any] = {
            "id": record.get("id") or record.get("__id") or record.get("legacyId"),
            "name": record.get("name") or "",
            "location": _format_location(record),
            "overall_quality": record.get("avgRatingRounded") or record.get("overallQuality") or record.get("overall"),
            "num_ratings": record.get("numRatings"),
            "reputation": record.get("reputation"),
            "safety": record.get("safety"),
            "happiness": record.get("happiness"),
            "facilities": record.get("facilities"),
            "social": record.get("social"),
            "location_rating": record.get("location"),
            "clubs": record.get("clubs"),
            "opportunities": record.get("opportunities"),
            "internet": record.get("internet"),
            "food": record.get("food"),
        }
        # RMP stores category bars in summary __ref (SchoolSummary): schoolReputation, schoolSafety, etc.
        summary_ref = record.get("summary")
        if _is_record_ref(summary_ref):
            summary_record = _resolve_ref(store, summary_ref)
            if isinstance(summary_record, dict):
                node["reputation"] = node["reputation"] or _safe_float(summary_record.get("schoolReputation"))
                node["safety"] = node["safety"] or _safe_float(summary_record.get("schoolSafety"))
                node["happiness"] = node["happiness"] or _safe_float(summary_record.get("schoolSatisfaction"))
                node["facilities"] = node["facilities"] or _safe_float(summary_record.get("campusCondition"))
                node["social"] = node["social"] or _safe_float(summary_record.get("socialActivities"))
                node["location_rating"] = node["location_rating"] or _safe_float(summary_record.get("campusLocation"))
                node["clubs"] = node["clubs"] or _safe_float(summary_record.get("clubAndEventActivities"))
                node["opportunities"] = node["opportunities"] or _safe_float(summary_record.get("careerOpportunities"))
                node["internet"] = node["internet"] or _safe_float(summary_record.get("internetSpeed"))
                node["food"] = node["food"] or _safe_float(summary_record.get("foodQuality"))
        return node

    def _parse_school_node(self, node: Mapping[str, Any]) -> School:
        """Build School from a dict (relay or nested)."""
        return School(
            id=str(node.get("id") or ""),
            name=node.get("name") or "",
            location=node.get("location") if isinstance(node.get("location"), str) else _format_location(node),
            overall_quality=_safe_float(node.get("overall_quality") or node.get("overallQuality") or node.get("overall")),
            num_ratings=_safe_int(node.get("num_ratings") or node.get("numRatings")),
            reputation=_safe_float(node.get("reputation")),
            safety=_safe_float(node.get("safety")),
            happiness=_safe_float(node.get("happiness")),
            facilities=_safe_float(node.get("facilities")),
            social=_safe_float(node.get("social")),
            location_rating=_safe_float(node.get("location_rating")) or (_safe_float(node.get("location")) if isinstance(node.get("location"), (int, float)) else None),
            clubs=_safe_float(node.get("clubs")),
            opportunities=_safe_float(node.get("opportunities")),
            internet=_safe_float(node.get("internet")),
            food=_safe_float(node.get("food")),
        )

    def _parse_school_rating_node(self, record: Mapping[str, Any]) -> SchoolRating:
        # RMP sends "2026-03-05 16:00:35 +0000 UTC"; use date part only.
        date_str = record.get("date")
        if isinstance(date_str, str) and " " in date_str:
            date_str = date_str.split(" ")[0]
        try:
            rating_date = date.fromisoformat(date_str) if isinstance(date_str, str) else date.today()
        except ValueError:
            rating_date = date.today()
        # RMP SchoolRating: reputationRating, locationRating, opportunitiesRating, facilitiesRating,
        # internetRating, foodRating, clubsRating, socialRating, happinessRating, safetyRating
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
            val = record.get(rmp_key)
            if val is not None:
                f = _safe_float(val)
                if f is not None:
                    if category_ratings is None:
                        category_ratings = {}
                    category_ratings[cat_key] = f
        if category_ratings is None:
            for key in ("reputation", "location", "opportunities", "facilities", "internet", "food", "clubs", "social", "happiness", "safety"):
                val = record.get(key) or record.get(key.replace("_", ""))
                if val is not None:
                    f = _safe_float(val)
                    if f is not None:
                        if category_ratings is None:
                            category_ratings = {}
                        category_ratings[key] = f
        overall = _safe_float(
            record.get("overall") or record.get("overallQuality") or record.get("quality")
        )
        if overall is None and category_ratings:
            overall = sum(category_ratings.values()) / len(category_ratings)
        thumbs_up = _safe_int(record.get("thumbsUpTotal") or record.get("thumbsUp") or record.get("thumbs_up"))
        thumbs_down = _safe_int(record.get("thumbsDownTotal") or record.get("thumbsDown") or record.get("thumbs_down"))
        helpful = _safe_int(record.get("helpful"))
        return SchoolRating(
            date=rating_date,
            comment=str(record.get("comment") or ""),
            overall=overall,
            category_ratings=category_ratings,
            helpful=helpful,
            thumbs_up=thumbs_up,
            thumbs_down=thumbs_down,
        )

    def get_school(self, school_id: str, *, use_compare_page: bool = False) -> School:
        """Fetch detailed information about a single school.

        Data is loaded from the school page HTML (or compare page if use_compare_page=True).
        """
        store = self._fetch_relay_store_for_school(school_id, use_compare_url=use_compare_page)
        record = get_school_node(store, school_id)
        if record is None:
            raise ParsingError(f"School record not found in __RELAY_STORE__ for id={school_id!r}")
        node = self._relay_school_to_node(store, record)
        return self._parse_school_node(node)

    def get_compare_schools(self, school_id_1: str, school_id_2: str) -> CompareSchoolsResult:
        """Fetch and compare two schools from the compare page (/compare/schools/id1/id2).

        Data is loaded from the compare page HTML; both schools include summary
        category ratings (reputation, safety, facilities, etc.) when present.
        """
        store = self._fetch_relay_store_for_compare_schools(school_id_1, school_id_2)
        record_1 = get_school_node(store, school_id_1)
        record_2 = get_school_node(store, school_id_2)
        if record_1 is None:
            raise ParsingError(f"School record not found in __RELAY_STORE__ for id={school_id_1!r}")
        if record_2 is None:
            raise ParsingError(f"School record not found in __RELAY_STORE__ for id={school_id_2!r}")
        node_1 = self._relay_school_to_node(store, record_1)
        node_2 = self._relay_school_to_node(store, record_2)
        return CompareSchoolsResult(
            school_1=self._parse_school_node(node_1),
            school_2=self._parse_school_node(node_2),
        )

    def _fetch_school_ratings_via_graphql(
        self,
        school_id: str,
        *,
        after: Optional[str] = None,
        first: int = 20,
    ) -> SchoolRatingsPage:
        """Fetch a page of school ratings from the GraphQL API (for cursor-based next pages)."""
        node_id = _school_node_id(school_id)
        variables: Dict[str, Any] = {"id": node_id, "first": first}
        if after is not None:
            variables["after"] = after
        payload = {"query": SCHOOL_RATINGS_QUERY, "variables": variables}
        data = self.raw_query(payload)
        node = (data.get("data") or {}).get("node")
        if not node:
            raise ParsingError("GraphQL response missing data.node (school not found or invalid id)")
        school = self._parse_school_node({
            "id": node.get("legacyId") or node.get("id"),
            "name": node.get("name"),
            "location": _format_location(node),
            "overall_quality": node.get("avgRatingRounded"),
            "num_ratings": node.get("numRatings"),
        })
        ratings_conn = node.get("ratings") or {}
        edges = ratings_conn.get("edges") or []
        page_info = ratings_conn.get("pageInfo") or {}
        ratings_models: List[SchoolRating] = []
        for edge in edges:
            r = edge.get("node") if isinstance(edge, dict) else None
            if isinstance(r, dict):
                ratings_models.append(self._parse_school_rating_node(r))
        has_next = bool(page_info.get("hasNextPage", False))
        next_cursor = page_info.get("endCursor") if page_info else None
        return SchoolRatingsPage(
            school=school,
            ratings=ratings_models,
            has_next_page=has_next,
            next_cursor=next_cursor,
        )

    def get_school_ratings_page(
        self,
        school_id: str,
        *,
        cursor: Optional[str] = None,
        page_size: int = 20,
    ) -> SchoolRatingsPage:
        """Fetch a single page of ratings for a school.

        First page is from the school page HTML. Subsequent pages are fetched
        via the GraphQL API using the returned next_cursor. Use iter_school_ratings
        to iterate all ratings.
        """
        if cursor is not None and not cursor.isdigit():
            return self._fetch_school_ratings_via_graphql(
                school_id, after=cursor, first=page_size
            )
        store = self._fetch_relay_store_for_school(school_id)
        record = get_school_node(store, school_id)
        if record is None:
            raise ParsingError(f"School record not found in __RELAY_STORE__ for id={school_id!r}")

        school = self._parse_school_node(self._relay_school_to_node(store, record))
        rating_records = get_school_ratings_from_store(store, record)
        if not rating_records:
            rating_records = get_all_school_rating_records(store)

        ratings_models: List[SchoolRating] = []
        for r in rating_records:
            ratings_models.append(self._parse_school_rating_node(r))

        page_info = get_school_ratings_connection_page_info(store, record)
        if cursor is not None and cursor.isdigit():
            start = max(0, int(cursor))
            page_slice = ratings_models[start : start + page_size]
            has_next = (start + page_size) < len(ratings_models)
            next_cursor = str(start + page_size) if has_next else None
        else:
            page_slice = ratings_models[:page_size]
            if page_info and page_info.get("hasNextPage") and page_info.get("endCursor"):
                has_next = True
                next_cursor = page_info.get("endCursor")
            else:
                has_next = len(ratings_models) > page_size
                next_cursor = str(page_size) if has_next else None

        return SchoolRatingsPage(
            school=school,
            ratings=page_slice,
            has_next_page=has_next,
            next_cursor=next_cursor,
        )

    def iter_school_ratings(
        self,
        school_id: str,
        *,
        page_size: int = 20,
        since: Optional[date] = None,
    ) -> Iterator[SchoolRating]:
        """Iterate ratings for a school, optionally stopping once `since` is reached."""
        cursor: Optional[str] = None
        while True:
            page = self.get_school_ratings_page(
                school_id=school_id,
                cursor=cursor,
                page_size=page_size,
            )
            for rating in page.ratings:
                if since is not None and rating.date <= since:
                    return
                yield rating
            if not page.has_next_page or not page.next_cursor:
                return
            cursor = page.next_cursor

    # ---- Internal helpers ------------------------------------------------------

    def _parse_professor_edge(self, edge: Mapping[str, Any]) -> Professor:
        node = edge.get("node", {})
        return self._parse_professor_node(node)

    def _parse_professor_node(self, node: Mapping[str, Any]) -> Professor:
        school_info = node.get("school")
        school: Optional[School] = None
        if isinstance(school_info, Mapping):
            school = School(
                id=str(school_info.get("id") or ""),
                name=school_info.get("name") or "",
                location=school_info.get("location") if isinstance(school_info.get("location"), str) else _format_location(school_info),
            )
        rating_dist = _build_rating_distribution(node.get("rating_distribution"))

        return Professor(
            id=str(node.get("id")),
            name=node.get("name") or "",
            department=node.get("department"),
            school=school,
            url=node.get("url"),
            overall_rating=_safe_float(node.get("overallRating")),
            num_ratings=_safe_int(node.get("numRatings")),
            percent_take_again=_safe_float(node.get("percentTakeAgain")),
            level_of_difficulty=_safe_float(node.get("levelOfDifficulty")),
            tags=[str(t) for t in (node.get("tags") or [])],
            rating_distribution=rating_dist,
        )

    def _parse_rating_node(self, node: Mapping[str, Any]) -> Rating:
        # RMP sends "2026-03-03 21:20:35 +0000 UTC"; use date part only.
        date_str = node.get("date")
        if isinstance(date_str, str) and " " in date_str:
            date_str = date_str.split(" ")[0]
        try:
            rating_date = date.fromisoformat(date_str) if isinstance(date_str, str) else date.today()
        except ValueError:
            rating_date = date.today()

        # Build details dict (for_credit, attendance, grade, textbook, etc.)
        details: Optional[Dict[str, Any]] = None
        key_to_snake = {"forCredit": "for_credit"}
        for key in ("for_credit", "forCredit", "attendance", "grade", "textbook"):
            val = node.get(key)
            if val is not None:
                if details is None:
                    details = {}
                details[key_to_snake.get(key, key)] = val
        helpful = _safe_int(node.get("helpful"))
        thumbs_up = _safe_int(node.get("thumbsUp") or node.get("thumbs_up"))
        thumbs_down = _safe_int(node.get("thumbsDown") or node.get("thumbs_down"))

        return Rating(
            date=rating_date,
            comment=str(node.get("comment") or ""),
            quality=_safe_float(node.get("quality")),
            difficulty=_safe_float(node.get("difficulty")),
            tags=[str(t) for t in (node.get("tags") or [])],
            course_raw=node.get("course") or None,
            details=details,
            helpful=helpful,
            thumbs_up=thumbs_up,
            thumbs_down=thumbs_down,
        )


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None

