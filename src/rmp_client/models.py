"""Data models for RateMyProfessors API responses.

All fields use snake_case. Numeric IDs are the legacy integer IDs visible
in RMP URLs; global Relay IDs are used internally only.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class School(BaseModel):
    """A school (university or college).

    Category fields (reputation, safety, etc.) are populated by ``get_school()``
    but may be absent on search results where only basic data is returned.
    """

    id: str
    name: str
    location: Optional[str] = None
    overall_quality: Optional[float] = None
    num_ratings: Optional[int] = None
    reputation: Optional[float] = None
    safety: Optional[float] = None
    happiness: Optional[float] = None
    facilities: Optional[float] = None
    social: Optional[float] = None
    location_rating: Optional[float] = None
    clubs: Optional[float] = None
    opportunities: Optional[float] = None
    internet: Optional[float] = None
    food: Optional[float] = None


class Professor(BaseModel):
    """A professor (teacher).

    ``tags`` and ``rating_distribution`` are always empty/null in the current
    GraphQL API responses; kept for forward compatibility.
    """

    id: str
    name: str
    department: Optional[str] = None
    school: Optional[School] = None
    overall_rating: Optional[float] = None
    num_ratings: Optional[int] = None
    percent_take_again: Optional[float] = None
    level_of_difficulty: Optional[float] = None
    tags: List[str] = []
    rating_distribution: Optional[Dict[int, RatingDistributionBucket]] = None


class RatingDistributionBucket(BaseModel):
    """One bucket in a professor's star-rating distribution."""

    count: int
    percentage: float


class Rating(BaseModel):
    """A single professor rating (review).

    ``quality`` maps to RMP's clarity/helpful rating; ``details`` may contain
    for_credit, attendance, grade, textbook when the API returns them.
    """

    date: date
    comment: str
    quality: Optional[float] = None
    difficulty: Optional[float] = None
    tags: List[str] = []
    course_raw: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    thumbs_up: Optional[int] = None
    thumbs_down: Optional[int] = None


class SchoolRating(BaseModel):
    """A single school rating (review).

    ``overall`` is computed as the average of all category scores.
    ``category_ratings`` maps category name to score.
    """

    date: date
    comment: str
    overall: Optional[float] = None
    category_ratings: Optional[Dict[str, float]] = None
    thumbs_up: Optional[int] = None
    thumbs_down: Optional[int] = None


class ProfessorRatingsPage(BaseModel):
    """One page of professor ratings with cursor pagination."""

    professor: Professor
    ratings: List[Rating]
    has_next_page: bool
    next_cursor: Optional[str] = None


class ProfessorSearchResult(BaseModel):
    """Paginated result from professor search or listing by school."""

    professors: List[Professor]
    total: Optional[int] = None
    page_size: int
    has_next_page: bool
    next_cursor: Optional[str] = None


class SchoolSearchResult(BaseModel):
    """Paginated result from school search."""

    schools: List[School]
    total: Optional[int] = None
    page_size: int
    has_next_page: bool
    next_cursor: Optional[str] = None


class CompareSchoolsResult(BaseModel):
    """Result of comparing two schools."""

    school_1: School
    school_2: School


class SchoolRatingsPage(BaseModel):
    """One page of school ratings with cursor pagination."""

    school: School
    ratings: List[SchoolRating]
    has_next_page: bool
    next_cursor: Optional[str] = None
