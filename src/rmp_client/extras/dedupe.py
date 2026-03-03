from __future__ import annotations

import re


def normalize_comment(text: str) -> str:
    """Lowercase and collapse whitespace for comment comparison."""
    return re.sub(r"\s+", " ", text.strip().lower())


def is_valid_comment(text: str, *, min_len: int = 10) -> bool:
    """Basic heuristic to filter out empty/very short comments."""
    return bool(text and len(text.strip()) >= min_len)

