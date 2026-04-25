"""RateMyProfessors API client -- public entry point."""

from .client import RMPClient
from .config import RMPClientConfig
from .errors import (
    ConfigurationError,
    HttpError,
    ParsingError,
    RetryError,
    RMPAPIError,
    RMPError,
)
from .rate_limit import TokenBucket
from .extras import (
    SentimentResult,
    analyze_sentiment,
    CommentIssue,
    ValidationResult,
    is_valid_comment,
    normalize_comment,
    build_course_mapping,
    clean_course_label,
)

__all__ = [
    "RMPClient",
    "RMPClientConfig",
    "RMPError",
    "ConfigurationError",
    "HttpError",
    "ParsingError",
    "RetryError",
    "RMPAPIError",
    "TokenBucket",
    "SentimentResult",
    "analyze_sentiment",
    "CommentIssue",
    "ValidationResult",
    "is_valid_comment",
    "normalize_comment",
    "build_course_mapping",
    "clean_course_label",
]
