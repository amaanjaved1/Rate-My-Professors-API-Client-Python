from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional

from .config import RMPClientConfig
from .errors import ParsingError
from .http import HttpClient, HttpClientContext
from .models import (
    Professor,
    ProfessorRatingsPage,
    ProfessorSearchResult,
    Rating,
    School,
    SchoolSearchResult,
)
from .relay_store import (
    extract_relay_store,
    get_professor_node,
    get_ratings_from_store,
    get_all_rating_records,
    _resolve_ref,
)


class RMPClient:
    """High-level client for RateMyProfessors.

    This is intentionally small for now; we will extend as we learn more about
    the underlying API shapes.
    """

    def __init__(self, config: Optional[RMPClientConfig] = None) -> None:
        self._config = config or RMPClientConfig.from_env()
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

    def search_schools(
        self,
        query: str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> SchoolSearchResult:
        """Search schools by name.

        NOTE: This uses a placeholder request body; you will need to adapt the
        payload once we lock in the actual RMP JSON/GraphQL contract.
        """
        # Placeholder GraphQL-like payload; adjust as we learn the real API
        variables: Dict[str, Any] = {
            "query": query,
            "page": page,
            "pageSize": page_size,
        }
        payload = {"operationName": "SearchSchools", "variables": variables, "query": "..."}
        data = self.raw_query(payload)

        # For now, expect a shape like {"data": {"schools": {"edges": [...], "pageInfo": ...}}}
        try:
            schools_raw: Iterable[Mapping[str, Any]] = data["data"]["schools"]["edges"]
        except Exception as exc:  # noqa: BLE001
            raise ParsingError(f"Unexpected school search payload: {data!r}") from exc

        schools: List[School] = []
        for edge in schools_raw:
            node = edge.get("node", {})
            schools.append(
                School(
                    id=str(node.get("id")),
                    name=node.get("name") or "",
                    city=node.get("city"),
                    state=node.get("state"),
                    country=node.get("country"),
                )
            )

        page_info = data["data"]["schools"].get("pageInfo", {})
        has_next = bool(page_info.get("hasNextPage", False))
        total = data["data"]["schools"].get("totalCount")

        return SchoolSearchResult(
            schools=schools,
            total=total,
            page=page,
            page_size=page_size,
            has_next_page=has_next,
        )

    # ---- Professor search / listing --------------------------------------------

    def search_professors(
        self,
        query: str,
        *,
        school_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ProfessorSearchResult:
        """Search professors by name and optional school.

        This is the general-purpose search entry point. For your use-case of
        scraping all professors at a school, use `list_professors_for_school`
        or `iter_professors_for_school`.
        """
        variables: Dict[str, Any] = {
            "query": query,
            "page": page,
            "pageSize": page_size,
        }
        if school_id is not None:
            variables["schoolId"] = school_id

        payload = {"operationName": "SearchProfessors", "variables": variables, "query": "..."}
        data = self.raw_query(payload)

        try:
            prof_edges: Iterable[Mapping[str, Any]] = data["data"]["professors"]["edges"]
        except Exception as exc:  # noqa: BLE001
            raise ParsingError(f"Unexpected professor search payload: {data!r}") from exc

        professors = [self._parse_professor_edge(edge) for edge in prof_edges]
        page_info = data["data"]["professors"].get("pageInfo", {})
        has_next = bool(page_info.get("hasNextPage", False))
        total = data["data"]["professors"].get("totalCount")

        return ProfessorSearchResult(
            professors=professors,
            total=total,
            page=page,
            page_size=page_size,
            has_next_page=has_next,
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
        base = self._config.professor_page_base.rstrip("/")
        return f"{base}/professor/{professor_id}"

    def _fetch_relay_store_for_professor(self, professor_id: str) -> Dict[str, Any]:
        """GET professor page HTML and return parsed __RELAY_STORE__."""
        url = self._professor_page_url(professor_id)
        html = self._client.get_html(url)
        try:
            return extract_relay_store(html)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ParsingError(f"Failed to extract __RELAY_STORE__ from professor page: {exc}") from exc

    def _relay_professor_to_node(self, store: Dict[str, Any], record: Mapping[str, Any]) -> Dict[str, Any]:
        """Convert a Relay Professor record to the shape _parse_professor_node expects."""
        node: Dict[str, Any] = {
            "id": record.get("id") or record.get("__id") or record.get("legacyId"),
            "name": record.get("name") or " ".join(filter(None, [record.get("firstName"), record.get("lastName")])),
            "department": record.get("department"),
            "url": record.get("url"),
            "overallRating": record.get("overallRating"),
            "numRatings": record.get("numRatings"),
            "percentTakeAgain": record.get("percentTakeAgain"),
            "levelOfDifficulty": record.get("levelOfDifficulty"),
            "tags": record.get("tags") or [],
        }
        school_val = record.get("school")
        if school_val is not None and isinstance(school_val, dict) and "__ref" in school_val:
            school_record = _resolve_ref(store, school_val)
            if school_record and isinstance(school_record, dict):
                node["school"] = {
                    "id": school_record.get("id") or school_record.get("__id"),
                    "name": school_record.get("name") or "",
                    "city": school_record.get("city"),
                    "state": school_record.get("state"),
                    "country": school_record.get("country"),
                }
        elif isinstance(school_val, dict):
            node["school"] = school_val
        return node

    def _relay_rating_to_node(self, record: Mapping[str, Any]) -> Dict[str, Any]:
        """Convert a Relay Rating record to the shape _parse_rating_node expects."""
        return {
            "date": record.get("date"),
            "comment": record.get("comment") or "",
            "quality": record.get("quality"),
            "difficulty": record.get("difficulty"),
            "tags": record.get("tags") or [],
            "course": record.get("course") or record.get("courseName"),
        }

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

    def get_professor_ratings_page(
        self,
        professor_id: str,
        *,
        cursor: Optional[str] = None,
        page_size: int = 20,
    ) -> ProfessorRatingsPage:
        """Fetch a single page of ratings/comments for a professor.

        Data is loaded from the professor page HTML (server-side rendered).
        Pagination is applied in-memory over the ratings embedded in the page.
        """
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

        # In-page pagination: cursor as offset index (or None for first page)
        start = int(cursor) if cursor is not None else 0
        start = max(0, start)
        page_slice = ratings_models[start : start + page_size]
        has_next = (start + page_size) < len(ratings_models)
        next_cursor = str(start + page_size) if has_next else None

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

    # ---- Internal helpers ------------------------------------------------------

    def _parse_professor_edge(self, edge: Mapping[str, Any]) -> Professor:
        node = edge.get("node", {})
        return self._parse_professor_node(node)

    def _parse_professor_node(self, node: Mapping[str, Any]) -> Professor:
        school_info = node.get("school")
        school: Optional[School] = None
        if isinstance(school_info, Mapping):
            school = School(
                id=str(school_info.get("id")),
                name=school_info.get("name") or "",
                city=school_info.get("city"),
                state=school_info.get("state"),
                country=school_info.get("country"),
            )

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
        )

    def _parse_rating_node(self, node: Mapping[str, Any]) -> Rating:
        # Expect an ISO date string; we keep parsing lenient and push strictness into models.
        date_str = node.get("date")
        try:
            rating_date = date.fromisoformat(date_str) if isinstance(date_str, str) else date.today()
        except ValueError:
            rating_date = date.today()

        return Rating(
            date=rating_date,
            comment=str(node.get("comment") or ""),
            quality=_safe_float(node.get("quality")),
            difficulty=_safe_float(node.get("difficulty")),
            tags=[str(t) for t in (node.get("tags") or [])],
            course_raw=node.get("course") or None,
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

