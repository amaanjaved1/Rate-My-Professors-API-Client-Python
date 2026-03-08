"""Tests for rmp_client.extras (dedupe, course_codes, sentiment)."""

from __future__ import annotations

import pytest

from rmp_client.extras.course_codes import build_course_mapping, clean_course_label
from rmp_client.extras.dedupe import is_valid_comment, normalize_comment


class TestNormalizeComment:
    """normalize_comment lowercases and collapses whitespace."""

    def test_lowercase_and_collapse(self) -> None:
        raw = "  Hello   World!  "
        assert normalize_comment(raw) == "hello world!"

    def test_empty_after_strip(self) -> None:
        assert normalize_comment("   ") == ""

    def test_single_word(self) -> None:
        assert normalize_comment("GREAT") == "great"

    def test_newlines_collapsed(self) -> None:
        assert normalize_comment("a\nb\nc") == "a b c"

    def test_unicode_preserved(self) -> None:
        assert normalize_comment("  Café  ") == "café"


class TestIsValidComment:
    """is_valid_comment filters by length."""

    def test_valid_min_len_default(self) -> None:
        assert is_valid_comment("this is ten!!") is True
        assert is_valid_comment("short") is False

    def test_empty_false(self) -> None:
        assert is_valid_comment("") is False
        assert is_valid_comment("   ") is False

    def test_custom_min_len(self) -> None:
        assert is_valid_comment("five!", min_len=5) is True
        assert is_valid_comment("four", min_len=5) is False

    def test_exactly_min_len(self) -> None:
        assert is_valid_comment("12345", min_len=5) is True


class TestCleanCourseLabel:
    """clean_course_label removes (n) and collapses whitespace."""

    def test_removes_count_parens(self) -> None:
        assert clean_course_label("MATH 101 (12)") == "MATH 101"
        assert clean_course_label("CS 50 (3)") == "CS 50"

    def test_collapses_whitespace(self) -> None:
        assert clean_course_label("  ANAT   215  ") == "ANAT 215"

    def test_no_parens_unchanged_except_trim(self) -> None:
        assert clean_course_label("MATH 101") == "MATH 101"


class TestBuildCourseMapping:
    """build_course_mapping maps scraped labels to valid course codes."""

    def test_exact_match_nospace(self) -> None:
        valid = ["MATH 101", "ANAT 215"]
        scraped = ["MATH 101", "math 101", "ANAT 215"]
        mapping = build_course_mapping(scraped, valid)
        assert mapping["MATH 101"] == {"MATH 101"}
        assert mapping["math 101"] == {"MATH 101"}
        assert mapping["ANAT 215"] == {"ANAT 215"}

    def test_prefix_number_match(self) -> None:
        valid = ["ANAT 215"]
        scraped = ["ANAT215", "anat 215"]
        mapping = build_course_mapping(scraped, valid)
        assert mapping.get("ANAT215") == {"ANAT 215"}
        assert mapping.get("anat 215") == {"ANAT 215"}

    def test_unknown_returns_none(self) -> None:
        valid = ["MATH 101"]
        scraped = ["UNKNOWN 999"]
        mapping = build_course_mapping(scraped, valid)
        assert mapping["UNKNOWN 999"] is None

    def test_empty_valid(self) -> None:
        mapping = build_course_mapping(["MATH 101"], [])
        assert mapping["MATH 101"] is None


class TestSentimentExtras:
    """analyze_sentiment requires textblob; test error when missing."""

    def test_analyze_sentiment_raises_without_textblob(self) -> None:
        from rmp_client.extras import sentiment as sentiment_mod

        if sentiment_mod.TextBlob is not None:
            pytest.skip("textblob is installed; cannot test missing dependency")
        from rmp_client.extras.sentiment import analyze_sentiment

        with pytest.raises(RuntimeError, match="textblob"):
            analyze_sentiment("Great professor!")
