from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class School(BaseModel):
    """A school on the RateMyProfessors website."""
    id: str
    name: str
    # Single location string (e.g. "Kingston, ON")
    location: Optional[str] = None
    # From school page: overall quality and category ratings (out of 5)
    overall_quality: Optional[float] = None
    num_ratings: Optional[int] = None
    reputation: Optional[float] = None
    safety: Optional[float] = None
    happiness: Optional[float] = None
    facilities: Optional[float] = None
    social: Optional[float] = None
    location_rating: Optional[float] = None  # "Location" category score out of 5
    clubs: Optional[float] = None
    opportunities: Optional[float] = None
    internet: Optional[float] = None
    food: Optional[float] = None


class Professor(BaseModel):
    """A professor on the RateMyProfessors website."""
    id: str
    name: str
    department: Optional[str] = None
    school: Optional[School] = None
    url: Optional[str] = None
    overall_rating: Optional[float] = None
    num_ratings: Optional[int] = None
    percent_take_again: Optional[float] = None
    level_of_difficulty: Optional[float] = None
    tags: List[str] = []
    # Rating distribution: key = level 1-5 (Awful=1 .. Awesome=5), value = {number of ratings, percentage of total ratings}
    rating_distribution: Optional[Dict[int, RatingDistributionBucket]] = None

class Rating(BaseModel):
    """A single professor rating/review."""

    date: date
    comment: str
    quality: Optional[float] = None
    difficulty: Optional[float] = None
    tags: List[str] = []
    course_raw: Optional[str] = None
    # Extra metadata: for_credit, attendance, grade, textbook, etc. Keys lowercase.
    details: Optional[Dict[str, Any]] = None
    helpful: Optional[int] = None
    thumbs_up: Optional[int] = None
    thumbs_down: Optional[int] = None

class RatingDistributionBucket(BaseModel):
    """The number of ratings and the percentage of ratings for a given rating level - 1 (lowest) to 5 (highest)."""

    count: int
    percentage: float

class ProfessorRatingsPage(BaseModel):
    """A page of ratings for a professor."""

    professor: Professor
    ratings: List[Rating]
    has_next_page: bool
    next_cursor: Optional[str] = None


class ProfessorSearchResult(BaseModel):
    """A page of search results for professors."""

    professors: List[Professor]
    total: Optional[int] = None
    page: int
    page_size: int
    has_next_page: bool
    next_cursor: Optional[str] = None  # from relay pageInfo.endCursor for next page


class SchoolSearchResult(BaseModel):
    """A page of search results for schools."""

    schools: List[School]
    total: Optional[int] = None
    page: int
    page_size: int
    has_next_page: bool
    next_cursor: Optional[str] = None  # from relay pageInfo.endCursor for next page


class CompareSchoolsResult(BaseModel):
    """Result of comparing two schools (from /compare/schools/id1/id2)."""

    school_1: School
    school_2: School


class SchoolRating(BaseModel):
    """A single rating/review on a school page.

    Each rating has an overall score (out of 5), optional category bars (out of 5),
    and optional thumbs/helpful counts.
    """

    date: date
    comment: str
    overall: Optional[float] = None
    # Category bars (out of 5): reputation, location, opportunities, facilities,
    # internet, food, clubs, social, happiness, safety. Keys lowercase.
    category_ratings: Optional[Dict[str, float]] = None
    helpful: Optional[int] = None
    thumbs_up: Optional[int] = None
    thumbs_down: Optional[int] = None


class SchoolRatingsPage(BaseModel):
    school: School
    ratings: List[SchoolRating]
    has_next_page: bool
    next_cursor: Optional[str] = None

