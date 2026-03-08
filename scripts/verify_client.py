#!/usr/bin/env python3
"""Verify the RMP client against the live site.

Fetches a known professor (Erin Meger, Queen's) and a page of ratings,
then prints key fields so you can confirm parsing matches the website.

Usage (from repo root):
  pip install -e .
  python scripts/verify_client.py

Or with PYTHONPATH:
  PYTHONPATH=src python scripts/verify_client.py
"""

from __future__ import annotations

import sys

from rmp_client import RMPClient


def main() -> int:
    # Professor we've aligned with (Erin Meger, Queen's University)
    professor_id = "2823076"

    print("Fetching professor page and parsing __RELAY_STORE__ ...")
    try:
        with RMPClient() as client:
            prof = client.get_professor(professor_id)
    except Exception as e:
        print(f"Failed to get professor: {e}", file=sys.stderr)
        return 1

    print("\n--- Professor ---")
    print(f"  id:          {prof.id}")
    print(f"  name:        {prof.name}")
    print(f"  department:  {prof.department}")
    if prof.school:
        print(f"  school:      {prof.school.name} ({prof.school.location or 'N/A'})")
    print(f"  rating:      {prof.overall_rating}/5")
    print(f"  num_ratings: {prof.num_ratings}")
    print(f"  would take again: {prof.percent_take_again}%")
    print(f"  difficulty:  {prof.level_of_difficulty}/5")
    if prof.tags:
        print(f"  tags:        {', '.join(prof.tags[:10])}{' ...' if len(prof.tags) > 10 else ''}")
    if prof.rating_distribution:
        print("  distribution (1-5):", end="")
        for level in sorted(prof.rating_distribution.keys()):
            b = prof.rating_distribution[level]
            print(f"  {level}={b.count}({b.percentage}%)", end="")
        print()

    print("\nFetching first page of ratings ...")
    try:
        with RMPClient() as client:
            page = client.get_professor_ratings_page(professor_id, page_size=5)
    except Exception as e:
        print(f"Failed to get ratings: {e}", file=sys.stderr)
        return 1

    print(f"\n--- Ratings (page size 5, has_next={page.has_next_page}) ---")
    for i, r in enumerate(page.ratings, 1):
        print(f"  {i}. {r.date} | quality={r.quality} difficulty={r.difficulty} | {r.course_raw or 'N/A'}")
        print(f"     {r.comment[:80]}{'...' if len(r.comment) > 80 else ''}")
        if r.tags:
            print(f"     tags: {', '.join(r.tags)}")

    print("\nDone. Client verification OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
