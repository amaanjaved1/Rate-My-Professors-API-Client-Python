"""
Example ingestion script that mirrors a Supabase-centric pipeline using RMPClient.

This is intentionally skeletal; wire it into your own Supabase schema and
deployment scripts as needed.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Mapping

from rmp_client import RMPClient
from rmp_client.extras.course_codes import build_course_mapping
from rmp_client.extras.dedupe import is_valid_comment, normalize_comment
from rmp_client.extras.sentiment import analyze_sentiment


SCHOOL_ID = 1466


def get_already_scraped_metadata() -> Mapping[str, date | None]:
    """Placeholder for a call into your Supabase `professors` table."""
    return {}


def get_valid_courses() -> Iterable[str]:
    """Placeholder for a call into your Supabase `courses` table."""
    return []


def main() -> None:
    existing = get_already_scraped_metadata()
    valid_courses = list(get_valid_courses())

    with RMPClient() as client:
        professors = list(client.iter_professors_for_school(SCHOOL_ID, page_size=50))

        for prof in professors:
            latest = existing.get(prof.name)

            ratings = list(
                client.iter_professor_ratings(
                    professor_id=prof.id,
                    since=latest,
                )
            )
            if not ratings:
                continue

            # Build course mapping
            scraped_labels = {r.course_raw or "general_course" for r in ratings}
            course_mapping = build_course_mapping(scraped_labels, valid_courses)

            for rating in ratings:
                if not is_valid_comment(rating.comment):
                    continue

                normalized_comment = normalize_comment(rating.comment)
                sentiment = analyze_sentiment(normalized_comment)

                mapped_courses = course_mapping.get(rating.course_raw or "general_course")
                course_codes = mapped_courses or {"general_course"}

                # At this point you would:
                # - upsert professor summary
                # - insert one row per (rating, course_code) into your rag_chunks table
                for code in course_codes:
                    _ = {
                        "text": normalized_comment,
                        "source": "ratemyprofessors",
                        "course_code": code,
                        "professor_name": prof.name,
                        "source_url": prof.url,
                        "tags": rating.tags,
                        "created_at": rating.date.isoformat(),
                        "quality_rating": rating.quality,
                        "difficulty_rating": rating.difficulty,
                        "sentiment_score": sentiment.score,
                        "sentiment_label": sentiment.label,
                    }
                    # replace this with a call to supabase.table("rag_chunks").insert(...)


if __name__ == "__main__":
    main()

