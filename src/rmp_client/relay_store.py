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


def get_professor_node(store: Dict[str, Any], professor_id: str) -> Optional[Dict[str, Any]]:
    """Find the Professor record in a Relay store by legacy ID (URL slug)."""
    professor_id_str = str(professor_id)
    for record in store.values():
        if not isinstance(record, dict):
            continue
        if record.get("__typename") != "Professor":
            continue
        # Match by id, __id, or legacyId (URL slug used in /professor/{legacyId})
        rid = record.get("id") or record.get("__id") or record.get("legacyId")
        if rid is None:
            continue
        if str(rid) == professor_id_str:
            return record
        # legacyId is often the slug in the URL
        if record.get("legacyId") == professor_id_str:
            return record
    return None


def get_ratings_from_store(
    store: Dict[str, Any],
    professor_record: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Extract rating records from the store for this professor.

    Handles Relay connection pattern: professor.ratings -> connection -> edges -> node (__ref).
    """
    ratings: List[Dict[str, Any]] = []
    ratings_field = professor_record.get("ratings")
    if ratings_field is None:
        return ratings

    # Connection record: { "edges": [ { "node": { "__ref": "..." } } ], ... }
    conn = ratings_field if isinstance(ratings_field, dict) else None
    if _is_record_ref(ratings_field):
        conn = _resolve_ref(store, ratings_field)
    if not conn:
        return ratings

    edges = conn.get("edges")
    if not isinstance(edges, list):
        return ratings

    for edge in edges:
        if not isinstance(edge, dict):
            continue
        node = edge.get("node")
        if _is_record_ref(node):
            rating_record = _resolve_ref(store, node)
            if rating_record and rating_record.get("__typename") in ("Rating", "ProfessorRating", "Review"):
                ratings.append(rating_record)
        elif isinstance(node, dict):
            ratings.append(node)

    return ratings


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
    """Find the School/University record in a Relay store by id."""
    sid = str(school_id)
    for key, record in store.items():
        if not isinstance(record, dict):
            continue
        if record.get("__typename") not in ("School", "University"):
            continue
        rid = record.get("id") or record.get("__id") or record.get("legacyId")
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


def get_school_ratings_from_store(
    store: Dict[str, Any],
    school_record: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Extract school rating records from the store (same connection pattern as professor ratings)."""
    ratings: List[Dict[str, Any]] = []
    ratings_field = school_record.get("ratings")
    if ratings_field is None:
        return ratings
    conn = ratings_field if isinstance(ratings_field, dict) else None
    if _is_record_ref(ratings_field):
        conn = _resolve_ref(store, ratings_field)
    if not conn:
        return ratings
    edges = conn.get("edges")
    if not isinstance(edges, list):
        return ratings
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        node = edge.get("node")
        if _is_record_ref(node):
            rating_record = _resolve_ref(store, node)
            if rating_record and rating_record.get("__typename") in (
                "Rating",
                "SchoolRating",
                "Review",
                "SchoolReview",
            ):
                ratings.append(rating_record)
        elif isinstance(node, dict):
            ratings.append(node)
    return ratings


def get_all_school_rating_records(store: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fallback: collect all records that look like school ratings from the store."""
    out: List[Dict[str, Any]] = []
    for record in store.values():
        if not isinstance(record, dict):
            continue
        if record.get("__typename") in ("Rating", "SchoolRating", "Review", "SchoolReview"):
            out.append(record)
    return out
