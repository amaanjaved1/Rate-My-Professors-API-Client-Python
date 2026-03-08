from .client import RMPClient
from .config import RMPClientConfig
from . import errors as _errors
from .extras import (
    SentimentResult,
    analyze_sentiment,
    is_valid_comment,
    normalize_comment,
    build_course_mapping,
    clean_course_label,
)

RMPError = _errors.RMPError

__all__ = [
    "RMPClient",
    "RMPClientConfig",
    "RMPError",
    "SentimentResult",
    "analyze_sentiment",
    "is_valid_comment",
    "normalize_comment",
    "build_course_mapping",
    "clean_course_label",
]

