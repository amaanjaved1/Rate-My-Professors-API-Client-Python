"""Tests for relay_store (__RELAY_STORE__ extraction and parsing)."""

from __future__ import annotations

import json

import pytest

from rmp_client.relay_store import (
    extract_relay_store,
    get_all_rating_records,
    get_professor_node,
    get_ratings_from_store,
)


def _html_with_store(store: dict) -> str:
    """Wrap a dict as window.__RELAY_STORE__ in script tag."""
    return f'<html><script>window.__RELAY_STORE__ = {json.dumps(store)};</script></html>'


class TestExtractRelayStore:
    """Extract __RELAY_STORE__ from HTML."""

    def test_extracts_valid_store(self) -> None:
        store = {"client:root": {"__id": "client:root"}, "node:1": {"__typename": "Professor", "id": "1"}}
        html = _html_with_store(store)
        result = extract_relay_store(html)
        assert result == store

    def test_extracts_nested_json(self) -> None:
        store = {"a": {"b": {"c": 1}}, "d": []}
        html = _html_with_store(store)
        result = extract_relay_store(html)
        assert result["a"]["b"]["c"] == 1
        assert result["d"] == []

    def test_raises_when_marker_missing(self) -> None:
        html = "<html><script>window.OTHER = {};</script></html>"
        with pytest.raises(ValueError, match="__RELAY_STORE__ not found"):
            extract_relay_store(html)

    def test_raises_on_invalid_json(self) -> None:
        html = "<html><script>window.__RELAY_STORE__ = { invalid };</script></html>"
        with pytest.raises(json.JSONDecodeError):
            extract_relay_store(html)

    def test_handles_strings_with_braces_inside(self) -> None:
        store = {"key": "value with { and }"}
        html = _html_with_store(store)
        result = extract_relay_store(html)
        assert result["key"] == "value with { and }"


class TestGetProfessorNode:
    """Find Professor record in store by id or legacyId."""

    def test_finds_by_id(self) -> None:
        store = {
            "node:abc": {"__typename": "Professor", "id": "abc", "name": "Jane"},
        }
        node = get_professor_node(store, "abc")
        assert node is not None
        assert node["name"] == "Jane"

    def test_finds_by_legacy_id(self) -> None:
        store = {
            "node:slug123": {"__typename": "Professor", "legacyId": "slug123", "name": "Bob"},
        }
        node = get_professor_node(store, "slug123")
        assert node is not None
        assert node["name"] == "Bob"

    def test_finds_teacher_by_legacy_id(self) -> None:
        """RMP professor page uses __typename Teacher and legacyId (int) for URL id."""
        store = {
            "VGVhY2hlci0yODIzMDc2": {
                "__typename": "Teacher",
                "legacyId": 2823076,
                "firstName": "Erin",
                "lastName": "Meger",
            },
        }
        node = get_professor_node(store, "2823076")
        assert node is not None
        assert node["firstName"] == "Erin"
        assert node["lastName"] == "Meger"

    def test_returns_none_when_not_found(self) -> None:
        store = {
            "node:1": {"__typename": "School", "id": "1"},
        }
        assert get_professor_node(store, "999") is None

    def test_ignores_non_professor_records(self) -> None:
        store = {
            "node:1": {"__typename": "Rating", "id": "1"},
        }
        assert get_professor_node(store, "1") is None

    def test_match_with_str_id(self) -> None:
        store = {
            "node:42": {"__typename": "Professor", "id": 42, "name": "Num"},
        }
        node = get_professor_node(store, "42")
        assert node is not None
        assert node["name"] == "Num"


class TestGetRatingsFromStore:
    """Extract ratings from professor's ratings connection."""

    def test_ratings_via_ref_connection(self) -> None:
        store = {
            "node:prof": {
                "__typename": "Professor",
                "id": "prof",
                "ratings": {"__ref": "conn:prof"},
            },
            "conn:prof": {
                "edges": [
                    {"node": {"__ref": "node:r1"}},
                    {"node": {"__ref": "node:r2"}},
                ],
            },
            "node:r1": {"__typename": "Rating", "id": "r1", "comment": "Good"},
            "node:r2": {"__typename": "Rating", "id": "r2", "comment": "OK"},
        }
        prof = store["node:prof"]
        ratings = get_ratings_from_store(store, prof)
        assert len(ratings) == 2
        assert ratings[0]["comment"] == "Good"
        assert ratings[1]["comment"] == "OK"

    def test_ratings_inline_edges(self) -> None:
        store = {
            "node:prof": {
                "__typename": "Professor",
                "ratings": {
                    "edges": [
                        {"node": {"__typename": "Rating", "comment": "A"}},
                        {"node": {"__typename": "ProfessorRating", "comment": "B"}},
                    ],
                },
            },
        }
        ratings = get_ratings_from_store(store, store["node:prof"])
        assert len(ratings) == 2
        assert ratings[0]["comment"] == "A"
        assert ratings[1]["comment"] == "B"

    def test_empty_when_no_ratings_field(self) -> None:
        prof = {"__typename": "Professor", "id": "1"}
        assert get_ratings_from_store({}, prof) == []

    def test_empty_when_edges_not_list(self) -> None:
        prof = {"__typename": "Professor", "ratings": {"edges": "not-a-list"}}
        assert get_ratings_from_store({}, prof) == []

    def test_ratings_via_edges_refs_rmp_style(self) -> None:
        """Real RMP store: ratings(first:5) is __ref, connection has edges.__refs."""
        store = {
            "Teacher-2823076": {
                "__typename": "Teacher",
                "legacyId": 2823076,
                "ratings(first:5)": {"__ref": "conn:2823076:ratings"},
            },
            "conn:2823076:ratings": {
                "__typename": "RatingConnection",
                "edges": {"__refs": ["edge:0", "edge:1"]},
            },
            "edge:0": {"node": {"__ref": "Rating-1"}},
            "edge:1": {"node": {"__ref": "Rating-2"}},
            "Rating-1": {"__typename": "Rating", "comment": "First", "clarityRating": 1},
            "Rating-2": {"__typename": "Rating", "comment": "Second", "clarityRating": 2},
        }
        prof = store["Teacher-2823076"]
        ratings = get_ratings_from_store(store, prof)
        assert len(ratings) == 2
        assert ratings[0]["comment"] == "First"
        assert ratings[1]["comment"] == "Second"


class TestGetAllRatingRecords:
    """Fallback: collect all rating-like records from store."""

    def test_collects_rating_typenames(self) -> None:
        store = {
            "node:r1": {"__typename": "Rating", "id": "r1"},
            "node:r2": {"__typename": "ProfessorRating", "id": "r2"},
            "node:r3": {"__typename": "Review", "id": "r3"},
            "node:p": {"__typename": "Professor", "id": "p"},
        }
        records = get_all_rating_records(store)
        assert len(records) == 3
        typenames = {r["__typename"] for r in records}
        assert typenames == {"Rating", "ProfessorRating", "Review"}

    def test_ignores_non_dict_values(self) -> None:
        store = {"node:r1": "string", "node:r2": {"__typename": "Rating"}}
        records = get_all_rating_records(store)
        assert len(records) == 1
