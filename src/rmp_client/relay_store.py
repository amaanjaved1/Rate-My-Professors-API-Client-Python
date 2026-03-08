"""Extract and parse window.__RELAY_STORE__ from RMP professor page HTML."""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Mapping, Optional


def extract_relay_store(html: str) -> Dict[str, Any]:
    """Extract window.__RELAY_STORE__ from professor page HTML and parse as JSON.

    Raises:
        ValueError: If __RELAY_STORE__ is not found or JSON is invalid.
    """
    marker = "window.__RELAY_STORE__"
    if marker not in html:
        raise ValueError("__RELAY_STORE__ not found in HTML")

    start = html.index(marker) + len(marker)
    # Skip " = "
    start = html.index("=", start) + 1
    # Find the start of the JSON object
    start = html.index("{", start)
    depth = 0
    end = start
    in_string = False
    escape = False
    quote = None
    i = start
    while i < len(html):
        c = html[i]
        if escape:
            escape = False
            i += 1
            continue
        if in_string:
            if c == "\\":
                escape = True
            elif c == quote:
                in_string = False
            i += 1
            continue
        if c in ('"', "'"):
            in_string = True
            quote = c
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1

    if depth != 0:
        raise ValueError("__RELAY_STORE__: unclosed JSON object")

    raw = html[start:end]
    return json.loads(raw)


def _is_record_ref(value: Any) -> bool:
    return isinstance(value, dict) and "__ref" in value and len(value) == 1


def _resolve_ref(store: Mapping[str, Any], ref: Dict[str, str]) -> Optional[Dict[str, Any]]:
    record_id = ref.get("__ref")
    if not record_id:
        return None
    return store.get(record_id) if isinstance(store.get(record_id), dict) else None


def _record_id(record: Mapping[str, Any]) -> Optional[str]:
    return record.get("__id") or record.get("id")


def _resolve_refs(store: Mapping[str, Any], ref_ids: List[str]) -> List[Dict[str, Any]]:
    """Resolve a list of record IDs to a list of records. Skips missing/invalid."""
    out: List[Dict[str, Any]] = []
    for ref_id in ref_ids or []:
        if not isinstance(ref_id, str):
            continue
        rec = store.get(ref_id)
        if isinstance(rec, dict):
            out.append(rec)
    return out


def get_professor_node(store: Dict[str, Any], professor_id: str) -> Optional[Dict[str, Any]]:
    """Find the Professor/Teacher record in a Relay store by legacy ID (URL slug)."""
    professor_id_str = str(professor_id)
    for record in store.values():
        if not isinstance(record, dict):
            continue
        # RMP uses __typename "Teacher" on the professor page
        if record.get("__typename") not in ("Professor", "Teacher"):
            continue
        # Match by legacyId (URL slug in /professor/{legacyId}) or id/__id
        legacy = record.get("legacyId")
        if legacy is not None and str(legacy) == professor_id_str:
            return record
        rid = record.get("id") or record.get("__id")
        if rid is not None and str(rid) == professor_id_str:
            return record
    return None


def _get_ratings_connection_ref(professor_record: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Get the ratings connection __ref from a professor/teacher record.

    RMP uses keys like "ratings(first:5)" or "ratings"; value is {"__ref": "..."}.
    """
    # Prefer exact key then any key that starts with "ratings"
    for key in ("ratings(first:5)", "ratings"):
        val = professor_record.get(key)
        if _is_record_ref(val):
            return val
    for key, val in professor_record.items():
        if key.startswith("ratings") and _is_record_ref(val):
            return val
    return None


def _edges_to_rating_records(
    store: Dict[str, Any], edges_value: Any
) -> List[Dict[str, Any]]:
    """Turn connection edges (list or __refs) into list of Rating record dicts."""
    ratings: List[Dict[str, Any]] = []
    edge_refs: List[str] = []
    if isinstance(edges_value, list):
        for edge in edges_value:
            if not isinstance(edge, dict):
                continue
            node = edge.get("node")
            if _is_record_ref(node):
                rec = _resolve_ref(store, node)
                if rec and rec.get("__typename") in ("Rating", "ProfessorRating", "Review"):
                    ratings.append(rec)
            elif isinstance(node, dict):
                ratings.append(node)
        return ratings
    # RMP uses edges: {"__refs": ["...edges:0", "...edges:1", ...]}
    if isinstance(edges_value, dict) and "__refs" in edges_value:
        edge_refs = edges_value.get("__refs") or []
    if not edge_refs:
        return ratings
    for ref_id in edge_refs:
        edge_record = store.get(ref_id) if isinstance(ref_id, str) else None
        if not isinstance(edge_record, dict):
            continue
        node = edge_record.get("node")
        if _is_record_ref(node):
            rating_record = _resolve_ref(store, node)
            if rating_record and rating_record.get("__typename") in ("Rating", "ProfessorRating", "Review"):
                ratings.append(rating_record)
        elif isinstance(node, dict):
            ratings.append(node)
    return ratings


def _get_professor_ratings_connection(
    store: Dict[str, Any], professor_record: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Resolve the ratings connection dict for a professor/teacher record."""
    ratings_ref = _get_ratings_connection_ref(professor_record)
    if ratings_ref is not None:
        return _resolve_ref(store, ratings_ref)
    ratings_field = professor_record.get("ratings")
    if isinstance(ratings_field, dict) and "edges" in ratings_field:
        return ratings_field
    return None


def get_professor_ratings_connection_page_info(
    store: Dict[str, Any], professor_record: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Return pageInfo (hasNextPage, endCursor) for the professor's ratings connection."""
    conn = _get_professor_ratings_connection(store, professor_record)
    if not isinstance(conn, dict):
        return None
    page_info_ref = conn.get("pageInfo")
    if not _is_record_ref(page_info_ref):
        return None
    info = _resolve_ref(store, page_info_ref)
    return info if isinstance(info, dict) else None


def get_ratings_from_store(
    store: Dict[str, Any],
    professor_record: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Extract rating records from the store for this professor.

    Handles Relay connection pattern: professor.ratings -> connection (or __ref) -> edges (list or __refs) -> node (__ref).
    """
    conn = _get_professor_ratings_connection(store, professor_record)
    if not conn:
        return []
    edges_value = conn.get("edges")
    return _edges_to_rating_records(store, edges_value)


def get_all_rating_records(store: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fallback: collect all records that look like ratings from the store."""
    out: List[Dict[str, Any]] = []
    for record in store.values():
        if not isinstance(record, dict):
            continue
        if record.get("__typename") in ("Rating", "ProfessorRating", "Review"):
            out.append(record)
    return out


def get_school_node(store: Dict[str, Any], school_id: str) -> Optional[Dict[str, Any]]:
    """Find the School/University record in a Relay store by legacy ID (URL slug) or id."""
    sid = str(school_id)
    for key, record in store.items():
        if not isinstance(record, dict):
            continue
        if record.get("__typename") not in ("School", "University"):
            continue
        # Match by legacyId first (URL slug in /school/{legacyId})
        legacy = record.get("legacyId")
        if legacy is not None and str(legacy) == sid:
            return record
        rid = record.get("id") or record.get("__id")
        if rid is not None and str(rid) == sid:
            return record
        try:
            decoded = base64.b64decode(key).decode("utf-8", errors="replace")
            if sid in decoded:
                return record
        except Exception:
            pass
        if sid in str(key):
            return record
    schools = [
        r
        for r in store.values()
        if isinstance(r, dict) and r.get("__typename") in ("School", "University")
    ]
    if len(schools) == 1:
        return schools[0]
    return None


def _get_school_ratings_connection_ref(school_record: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Get the ratings connection __ref from a school record.

    RMP uses keys like "ratings(first:5)" or "ratings"; value is {"__ref": "..."}.
    """
    for key in ("ratings(first:5)", "ratings"):
        val = school_record.get(key)
        if _is_record_ref(val):
            return val
    for key, val in school_record.items():
        if key.startswith("ratings") and _is_record_ref(val):
            return val
    return None


def _edges_to_school_rating_records(
    store: Dict[str, Any], edges_value: Any
) -> List[Dict[str, Any]]:
    """Turn connection edges (list or __refs) into list of SchoolRating record dicts."""
    ratings: List[Dict[str, Any]] = []
    school_typenames = ("SchoolRating", "Rating", "SchoolReview", "Review")
    edge_refs: List[str] = []
    if isinstance(edges_value, list):
        for edge in edges_value:
            if not isinstance(edge, dict):
                continue
            node = edge.get("node")
            if _is_record_ref(node):
                rec = _resolve_ref(store, node)
                if rec and rec.get("__typename") in school_typenames:
                    ratings.append(rec)
            elif isinstance(node, dict):
                ratings.append(node)
        return ratings
    if isinstance(edges_value, dict) and "__refs" in edges_value:
        edge_refs = edges_value.get("__refs") or []
    if not edge_refs:
        return ratings
    for ref_id in edge_refs:
        edge_record = store.get(ref_id) if isinstance(ref_id, str) else None
        if not isinstance(edge_record, dict):
            continue
        node = edge_record.get("node")
        if _is_record_ref(node):
            rating_record = _resolve_ref(store, node)
            if rating_record and rating_record.get("__typename") in school_typenames:
                ratings.append(rating_record)
        elif isinstance(node, dict):
            ratings.append(node)
    return ratings


def _get_school_ratings_connection(
    store: Dict[str, Any], school_record: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Resolve the ratings connection dict for a school record."""
    ratings_ref = _get_school_ratings_connection_ref(school_record)
    if ratings_ref is not None:
        return _resolve_ref(store, ratings_ref)
    ratings_field = school_record.get("ratings")
    if isinstance(ratings_field, dict) and "edges" in ratings_field:
        return ratings_field
    if _is_record_ref(ratings_field):
        return _resolve_ref(store, ratings_field)
    return None


def get_school_ratings_connection_page_info(
    store: Dict[str, Any], school_record: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Return pageInfo (hasNextPage, endCursor) for the school's ratings connection."""
    conn = _get_school_ratings_connection(store, school_record)
    if not isinstance(conn, dict):
        return None
    page_info_ref = conn.get("pageInfo")
    if not _is_record_ref(page_info_ref):
        return None
    info = _resolve_ref(store, page_info_ref)
    return info if isinstance(info, dict) else None


def get_school_ratings_from_store(
    store: Dict[str, Any],
    school_record: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Extract school rating records from the store.

    Handles Relay pattern: school.ratings(first:5) -> connection -> edges (list or __refs) -> node (__ref).
    """
    conn = _get_school_ratings_connection(store, school_record)
    if not conn:
        return []
    edges_value = conn.get("edges")
    return _edges_to_school_rating_records(store, edges_value)


def get_all_school_rating_records(store: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fallback: collect all records that look like school ratings from the store."""
    out: List[Dict[str, Any]] = []
    for record in store.values():
        if not isinstance(record, dict):
            continue
        if record.get("__typename") in ("Rating", "SchoolRating", "Review", "SchoolReview"):
            out.append(record)
    return out


# ---- Professor search page (search/professors/?q=...) ------------------------------------------


def get_teacher_search_connection(store: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Get the TeacherSearchConnectionConnection from a search page relay store.

    Root has newSearch __ref -> newSearch record has teachers(...) __ref -> connection.
    """
    root = store.get("client:root")
    if not isinstance(root, dict):
        return None
    new_search_ref = root.get("newSearch")
    if not _is_record_ref(new_search_ref):
        return None
    new_search = _resolve_ref(store, new_search_ref)
    if not isinstance(new_search, dict):
        return None
    for key, val in new_search.items():
        if key.startswith("teachers(") and _is_record_ref(val):
            conn = _resolve_ref(store, val)
            if isinstance(conn, dict) and conn.get("edges") is not None:
                return conn
    return None


def _edges_to_teacher_records(
    store: Dict[str, Any], edges_value: Any
) -> List[Dict[str, Any]]:
    """Turn connection edges (list or __refs) into list of Teacher/Professor record dicts."""
    teachers: List[Dict[str, Any]] = []
    teacher_typenames = ("Teacher", "Professor")
    edge_refs: List[str] = []
    if isinstance(edges_value, list):
        for edge in edges_value:
            if not isinstance(edge, dict):
                continue
            node = edge.get("node")
            if _is_record_ref(node):
                rec = _resolve_ref(store, node)
                if rec and rec.get("__typename") in teacher_typenames:
                    teachers.append(rec)
            elif isinstance(node, dict) and node.get("__typename") in teacher_typenames:
                teachers.append(node)
        return teachers
    if isinstance(edges_value, dict) and "__refs" in edges_value:
        edge_refs = edges_value.get("__refs") or []
    if not edge_refs:
        return teachers
    for ref_id in edge_refs:
        edge_record = store.get(ref_id) if isinstance(ref_id, str) else None
        if not isinstance(edge_record, dict):
            continue
        node = edge_record.get("node")
        if _is_record_ref(node):
            rec = _resolve_ref(store, node)
            if rec and rec.get("__typename") in teacher_typenames:
                teachers.append(rec)
        elif isinstance(node, dict) and node.get("__typename") in teacher_typenames:
            teachers.append(node)
    return teachers


def get_teacher_search_result_count(connection: Dict[str, Any]) -> Optional[int]:
    """Get resultCount from TeacherSearchConnectionConnection (total matches)."""
    val = connection.get("resultCount")
    return int(val) if val is not None else None


def get_teacher_search_page_info(
    store: Dict[str, Any], connection: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Resolve pageInfo __ref from connection; return dict with hasNextPage, endCursor."""
    page_info_ref = connection.get("pageInfo")
    if not _is_record_ref(page_info_ref):
        return None
    info = _resolve_ref(store, page_info_ref)
    if not isinstance(info, dict):
        return None
    return info


# ---- School search page (search/schools?q=...) ----------------------------------------------


def get_school_search_connection(store: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Get the SchoolSearchConnectionConnection from a search page relay store.

    Root has newSearch __ref -> newSearch record has schools(...) __ref -> connection.
    """
    root = store.get("client:root")
    if not isinstance(root, dict):
        return None
    new_search_ref = root.get("newSearch")
    if not _is_record_ref(new_search_ref):
        return None
    new_search = _resolve_ref(store, new_search_ref)
    if not isinstance(new_search, dict):
        return None
    for key, val in new_search.items():
        if key.startswith("schools(") and _is_record_ref(val):
            conn = _resolve_ref(store, val)
            if isinstance(conn, dict) and conn.get("edges") is not None:
                return conn
    return None


def _edges_to_school_records(
    store: Dict[str, Any], edges_value: Any
) -> List[Dict[str, Any]]:
    """Turn connection edges (list or __refs) into list of School record dicts."""
    schools: List[Dict[str, Any]] = []
    school_typenames = ("School", "University")
    edge_refs: List[str] = []
    if isinstance(edges_value, list):
        for edge in edges_value:
            if not isinstance(edge, dict):
                continue
            node = edge.get("node")
            if _is_record_ref(node):
                rec = _resolve_ref(store, node)
                if rec and rec.get("__typename") in school_typenames:
                    schools.append(rec)
            elif isinstance(node, dict) and node.get("__typename") in school_typenames:
                schools.append(node)
        return schools
    if isinstance(edges_value, dict) and "__refs" in edges_value:
        edge_refs = edges_value.get("__refs") or []
    if not edge_refs:
        return schools
    for ref_id in edge_refs:
        edge_record = store.get(ref_id) if isinstance(ref_id, str) else None
        if not isinstance(edge_record, dict):
            continue
        node = edge_record.get("node")
        if _is_record_ref(node):
            rec = _resolve_ref(store, node)
            if rec and rec.get("__typename") in school_typenames:
                schools.append(rec)
        elif isinstance(node, dict) and node.get("__typename") in school_typenames:
            schools.append(node)
    return schools


def get_school_search_result_count(connection: Dict[str, Any]) -> Optional[int]:
    """Get resultCount from SchoolSearchConnectionConnection (total matches)."""
    val = connection.get("resultCount")
    return int(val) if val is not None else None


def get_school_search_page_info(
    store: Dict[str, Any], connection: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Resolve pageInfo __ref from connection; return dict with hasNextPage, endCursor."""
    page_info_ref = connection.get("pageInfo")
    if not _is_record_ref(page_info_ref):
        return None
    info = _resolve_ref(store, page_info_ref)
    if not isinstance(info, dict):
        return None
    return info
