from __future__ import annotations

import re
from typing import Dict, Iterable, Optional, Set


def clean_course_label(raw: str) -> str:
    """Clean a single course label scraped from RMP (remove counts, trim)."""
    # drop things like "(12)" and collapse whitespace
    cleaned = re.sub(r"\(\d+\)", "", raw)
    return re.sub(r"\s+", " ", cleaned).strip()


def build_course_mapping(
    scraped_labels: Iterable[str],
    valid_courses: Iterable[str],
) -> Dict[str, Optional[Set[str]]]:
    """Rudimentary mapping from scraped labels -> known valid course codes.

    This is a simplified, generalized version of your two-pass logic:
    - normalise both scraped labels and valid course codes
    - attempt exact and prefix+number matches

    Returns a dict of scraped label -> set of matching valid codes (or None if ambiguous/unknown).
    """
    valid_set = {vc.strip().upper() for vc in valid_courses}
    by_nospace = {vc.replace(" ", ""): vc for vc in valid_set}

    mapping: Dict[str, Optional[Set[str]]] = {}

    for raw in scraped_labels:
        cleaned = clean_course_label(raw)
        key = cleaned.replace(" ", "").upper()

        # exact nospace match
        if key in by_nospace:
            mapping[raw] = {by_nospace[key]}
            continue

        # try simple prefix+3-digit patterns: ANAT215 -> ANAT 215
        prefix_match = re.match(r"^[A-Z]+", key)
        num_match = re.search(r"(\d{3})", key)

        candidates: Set[str] = set()
        if prefix_match and num_match:
            prefix = prefix_match.group(0)
            num = num_match.group(1)
            candidate = f"{prefix} {num}"
            if candidate in valid_set:
                candidates.add(candidate)

        mapping[raw] = candidates or None

    return mapping

