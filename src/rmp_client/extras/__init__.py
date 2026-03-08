# Ingestion helpers: sentiment, dedupe, course_codes.
# Re-exported from rmp_client so you can: from rmp_client import analyze_sentiment, ...

from .sentiment import SentimentResult, analyze_sentiment
from .dedupe import is_valid_comment, normalize_comment
from .course_codes import build_course_mapping, clean_course_label

__all__ = [
    "SentimentResult",
    "analyze_sentiment",
    "is_valid_comment",
    "normalize_comment",
    "build_course_mapping",
    "clean_course_label",
]
