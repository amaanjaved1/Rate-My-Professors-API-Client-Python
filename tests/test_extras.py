"""Tests for extras: helpers, course_codes, sentiment."""

from __future__ import annotations

from rmp_client import (
    build_course_mapping,
    clean_course_label,
    is_valid_comment,
    normalize_comment,
)


class TestNormalizeComment:
    """normalize_comment."""

    def test_lowercases_and_collapses_whitespace(self) -> None:
        assert normalize_comment("  Hello   World!  ") == "hello world!"

    def test_empty_after_strip(self) -> None:
        assert normalize_comment("   ") == ""

    def test_single_word(self) -> None:
        assert normalize_comment("GREAT") == "great"

    def test_newlines_collapsed(self) -> None:
        assert normalize_comment("a\nb\nc") == "a b c"

    def test_unicode_preserved(self) -> None:
        assert normalize_comment("  Café  ") == "café"

    def test_strips_html_by_default(self) -> None:
        assert normalize_comment("<b>Loved</b> this class") == "loved this class"

    def test_decodes_html_entities(self) -> None:
        assert normalize_comment("great &amp; easy") == "great & easy"
        assert normalize_comment("<b>bold</b> &amp; great") == "bold & great"

    def test_strip_html_option(self) -> None:
        assert normalize_comment("<b>Bold</b>", strip_html=False) == "<b>bold</b>"

    def test_strip_punctuation_option(self) -> None:
        assert normalize_comment("Hello, world!", strip_punctuation=True) == "hello world"


class TestIsValidComment:
    """is_valid_comment."""

    def test_valid_with_default_min_len(self) -> None:
        assert is_valid_comment("this is ten!!").valid is True
        assert is_valid_comment("short").valid is False

    def test_empty_is_false(self) -> None:
        assert is_valid_comment("").valid is False
        assert is_valid_comment("   ").valid is False

    def test_custom_min_len(self) -> None:
        assert is_valid_comment("five!", min_len=5).valid is True
        assert is_valid_comment("four", min_len=5).valid is False

    def test_exactly_min_len_with_alpha(self) -> None:
        assert is_valid_comment("hello", min_len=5).valid is True

    def test_returns_issues_for_invalid_comments(self) -> None:
        short = is_valid_comment("short")
        assert short.valid is False
        assert any(i.code == "too_short" for i in short.issues)

        all_caps = is_valid_comment("WORST PROF EVER")
        assert all_caps.valid is False
        assert any(i.code == "all_caps" for i in all_caps.issues)

        no_alpha = is_valid_comment("12345", min_len=5)
        assert no_alpha.valid is False
        assert any(i.code == "no_alpha" for i in no_alpha.issues)

        excessive = is_valid_comment("sooooooo bad")
        assert excessive.valid is False
        assert any(i.code == "excessive_repeats" for i in excessive.issues)


class TestCleanCourseLabel:
    """clean_course_label."""

    def test_removes_count_parens(self) -> None:
        assert clean_course_label("MATH 101 (12)") == "MATH 101"
        assert clean_course_label("CS 50 (3)") == "CS 50"

    def test_collapses_whitespace(self) -> None:
        assert clean_course_label("  ANAT   215  ") == "ANAT 215"

    def test_no_parens_unchanged_except_trim(self) -> None:
        assert clean_course_label("MATH 101") == "MATH 101"


class TestBuildCourseMapping:
    """build_course_mapping."""

    def test_exact_match_case_insensitive(self) -> None:
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
        assert mapping["ANAT215"] == {"ANAT 215"}
        assert mapping["anat 215"] == {"ANAT 215"}

    def test_unknown_returns_none(self) -> None:
        valid = ["MATH 101"]
        scraped = ["UNKNOWN 999"]
        mapping = build_course_mapping(scraped, valid)
        assert mapping["UNKNOWN 999"] is None

    def test_empty_valid(self) -> None:
        mapping = build_course_mapping(["MATH 101"], [])
        assert mapping["MATH 101"] is None

    def test_four_digit_course_number_match(self) -> None:
        valid = ["MATH 1001", "CS 1102"]
        scraped = ["MATH1001", "CS1102"]
        mapping = build_course_mapping(scraped, valid)
        assert mapping["MATH1001"] == {"MATH 1001"}
        assert mapping["CS1102"] == {"CS 1102"}
