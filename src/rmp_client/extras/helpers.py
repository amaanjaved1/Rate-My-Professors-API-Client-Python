"""Helpers for normalizing and validating rating comments."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Literal


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode HTML entities from text."""
    return html.unescape(re.sub(r"<[^>]*>", "", text))


def normalize_comment(
    text: str,
    *,
    strip_html: bool = True,
    strip_punctuation: bool = False,
) -> str:
    """Normalize a comment for comparison or deduplication.

    - Trims leading/trailing whitespace
    - Strips HTML tags (opt-out via *strip_html*)
    - Lowercases
    - Collapses runs of whitespace to a single space
    - Optionally strips punctuation for looser matching
    """
    out = text.strip()
    if strip_html:
        out = _strip_html(out)
    out = re.sub(r"\s+", " ", out.lower())
    if strip_punctuation:
        out = re.sub(r"[^\w\s]", "", out)
    return out


IssueCode = Literal[
    "empty",
    "too_short",
    "all_caps",
    "excessive_repeats",
    "no_alpha",
]


@dataclass
class CommentIssue:
    code: IssueCode
    message: str


@dataclass
class ValidationResult:
    valid: bool
    issues: list[CommentIssue] = field(default_factory=list)


def is_valid_comment(text: str, *, min_len: int = 10) -> ValidationResult:
    """Validate a comment and return detailed diagnostics.

    Checks for:
    - Empty or whitespace-only text
    - Below minimum length (*min_len*, default 10)
    - All uppercase (shouting)
    - Excessive repeated characters (e.g. "aaaaaaa")
    - No alphabetic characters at all
    """
    issues: list[CommentIssue] = []
    trimmed = (text or "").strip()

    if not trimmed:
        issues.append(CommentIssue(code="empty", message="Comment is empty"))
        return ValidationResult(valid=False, issues=issues)

    if len(trimmed) < min_len:
        issues.append(
            CommentIssue(
                code="too_short",
                message=f"Comment is {len(trimmed)} chars (minimum {min_len})",
            )
        )

    if len(trimmed) > 3 and trimmed == trimmed.upper() and re.search(r"[A-Z]", trimmed):
        issues.append(CommentIssue(code="all_caps", message="Comment is all uppercase"))

    if re.search(r"(.)\1{4,}", trimmed, re.IGNORECASE):
        issues.append(
            CommentIssue(
                code="excessive_repeats",
                message="Comment contains excessive repeated characters",
            )
        )

    if not re.search(r"[a-zA-Z]", trimmed):
        issues.append(
            CommentIssue(code="no_alpha", message="Comment contains no alphabetic characters")
        )

    return ValidationResult(valid=len(issues) == 0, issues=issues)
