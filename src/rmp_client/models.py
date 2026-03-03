from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class School(BaseModel):
    id: str
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class Professor(BaseModel):
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


class RatingSummary(BaseModel):
    overall_rating: Optional[float] = None
    num_ratings: int
    percent_take_again: Optional[float] = None
    level_of_difficulty: Optional[float] = None


class Rating(BaseModel):
    date: date
    comment: str
    quality: Optional[float] = None
    difficulty: Optional[float] = None
    tags: List[str] = []
    course_raw: Optional[str] = None


class ProfessorRatingsPage(BaseModel):
    professor: Professor
    ratings: List[Rating]
    has_next_page: bool
    next_cursor: Optional[str] = None


class ProfessorSearchResult(BaseModel):
    professors: List[Professor]
    total: Optional[int] = None
    page: int
    page_size: int
    has_next_page: bool


class SchoolSearchResult(BaseModel):
    schools: List[School]
    total: Optional[int] = None
    page: int
    page_size: int
    has_next_page: bool

