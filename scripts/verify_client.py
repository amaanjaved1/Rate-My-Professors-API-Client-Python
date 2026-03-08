#!/usr/bin/env python3
"""Verify the RMP client against the live site.

Fetches a known professor (Erin Meger, Queen's) and school (Queen's 1466),
plus professor/school search, compare schools, and up to N pages of ratings
for each, then prints key fields so you can confirm parsing matches the website.

The first page of ratings comes from the HTML; subsequent pages are fetched
via the site's GraphQL API, so you can scrape all ratings by using a high
--max-pages or iter_professor_ratings / iter_school_ratings in code.

Usage (from repo root):
  pip install -e .
  python scripts/verify_client.py              # up to 3 pages of ratings each (default)
  python scripts/verify_client.py --page-size 20
  python scripts/verify_client.py --max-pages 10  # fetch up to 10 pages each

Or with PYTHONPATH:
  PYTHONPATH=src python scripts/verify_client.py
"""

from __future__ import annotations

import argparse
import sys

from rmp_client import RMPClient
from rmp_client.errors import RMPAPIError


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify RMP client against the live site.")
    p.add_argument(
        "--page-size",
        "-n",
        type=int,
        default=5,
        metavar="N",
        help="Number of ratings per page (default: 5)",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=3,
        metavar="N",
        help="Max pages of professor/school ratings to fetch (default: 3; first from HTML, rest via GraphQL)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    page_size = max(1, args.page_size)
    max_pages = max(1, args.max_pages)

    professor_id = "2823076"  # Erin Meger, Queen's University
    school_id = "1466"        # Queen's University at Kingston

    try:
        with RMPClient() as client:
            # ---- Professor ----
            print("Fetching professor page ...")
            prof = client.get_professor(professor_id)

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

            print(f"\nFetching up to {max_pages} page(s) of professor ratings (page_size={page_size}) ...")
            prof_total = 0
            cursor: str | None = None
            for page_num in range(max_pages):
                prof_page = client.get_professor_ratings_page(
                    professor_id, cursor=cursor, page_size=page_size
                )
                label = f"--- Professor ratings (page {page_num + 1}, has_next={prof_page.has_next_page}) ---"
                print(label)
                for i, r in enumerate(prof_page.ratings, 1):
                    idx = prof_total + i
                    print(f"  {idx}. {r.date} | quality={r.quality} difficulty={r.difficulty} | {r.course_raw or 'N/A'}")
                    print(f"     {r.comment[:80]}{'...' if len(r.comment) > 80 else ''}")
                    if r.tags:
                        print(f"     tags: {', '.join(r.tags)}")
                prof_total += len(prof_page.ratings)
                if not prof_page.has_next_page or not prof_page.next_cursor:
                    break
                cursor = prof_page.next_cursor
            print(f"  (shown {prof_total} professor ratings)")

            # ---- Professor search ----
            print("\nSearching professors (q=test) ...")
            search_result = client.search_professors("test")
            print(f"--- Professor search: total={search_result.total} has_next={search_result.has_next_page} ---")
            for i, p in enumerate(search_result.professors[:5], 1):
                school_name = p.school.name if p.school else "N/A"
                print(f"  {i}. {p.name} | {p.department or 'N/A'} @ {school_name} | rating={p.overall_rating} n={p.num_ratings}")

            # ---- School search ----
            print("\nSearching schools (q=queens) ...")
            school_search = client.search_schools("queens")
            print(f"--- School search: total={school_search.total} has_next={school_search.has_next_page} ---")
            for i, s in enumerate(school_search.schools[:5], 1):
                print(f"  {i}. {s.name} | {s.location or 'N/A'} | quality={s.overall_quality} n={s.num_ratings}")

            # ---- School ----
            print("\nFetching school page ...")
            school = client.get_school(school_id)

            print("\n--- School ---")
            print(f"  id:              {school.id}")
            print(f"  name:            {school.name}")
            print(f"  location:        {school.location or 'N/A'}")
            print(f"  overall_quality: {school.overall_quality}/5")
            print(f"  num_ratings:     {school.num_ratings}")
            cats = []
            for k in ("reputation", "safety", "happiness", "facilities", "social", "location_rating", "clubs", "opportunities", "internet", "food"):
                v = getattr(school, k, None)
                if v is not None:
                    cats.append(f"{k}={v}")
            if cats:
                print(f"  categories:      {', '.join(cats)}")

            print(f"\nFetching up to {max_pages} page(s) of school ratings (page_size={page_size}) ...")
            school_total = 0
            cursor = None
            for page_num in range(max_pages):
                school_page = client.get_school_ratings_page(
                    school_id, cursor=cursor, page_size=page_size
                )
                label = f"--- School ratings (page {page_num + 1}, has_next={school_page.has_next_page}) ---"
                print(label)
                for i, r in enumerate(school_page.ratings, 1):
                    idx = school_total + i
                    overall_str = f" overall={r.overall}" if r.overall is not None else ""
                    print(f"  {idx}. {r.date}{overall_str}")
                    print(f"     {r.comment[:80]}{'...' if len(r.comment) > 80 else ''}")
                    if r.category_ratings:
                        parts = [f"{k}={v}" for k, v in list(r.category_ratings.items())[:5]]
                        print(f"     categories: {', '.join(parts)}{' ...' if len(r.category_ratings) > 5 else ''}")
                school_total += len(school_page.ratings)
                if not school_page.has_next_page or not school_page.next_cursor:
                    break
                cursor = school_page.next_cursor
            print(f"  (shown {school_total} school ratings)")

            # ---- Compare schools ----
            print("\nFetching compare schools (1466 vs 1491) ...")
            compare = client.get_compare_schools("1466", "1491")
            print("--- Compare schools ---")
            cat_keys = ("reputation", "safety", "happiness", "facilities", "social", "location_rating", "clubs", "opportunities", "internet", "food")
            for label, s in [("School 1", compare.school_1), ("School 2", compare.school_2)]:
                print(f"\n  {label}: {s.name}")
                print(f"    id:              {s.id}")
                print(f"    location:        {s.location or 'N/A'}")
                print(f"    overall_quality: {s.overall_quality}/5")
                print(f"    num_ratings:     {s.num_ratings}")
                cats = [f"{k}={getattr(s, k)}" for k in cat_keys if getattr(s, k, None) is not None]
                if cats:
                    print(f"    categories:      {', '.join(cats)}")

    except RMPAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        if e.details:
            import json
            print("API error details:", file=sys.stderr)
            print(json.dumps(e.details, indent=2), file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print("\nDone. Client verification OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
