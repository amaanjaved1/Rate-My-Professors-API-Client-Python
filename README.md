# RateMyProfessors API Client (Python)

[![PyPI](https://img.shields.io/pypi/v/ratemyprofessors-client?color=10b981&cacheSeconds=300)](https://pypi.org/project/ratemyprofessors-client/) [![downloads](https://img.shields.io/pepy/dt/ratemyprofessors-client?cacheSeconds=300)](https://pypi.org/project/ratemyprofessors-client/) [![docs](https://img.shields.io/badge/docs-website-10b981?cacheSeconds=300)](https://amaanjaved1.github.io/Rate-My-Professors-API-Client-Python/)

A typed, retrying, rate-limited **unofficial** client for [RateMyProfessors](https://www.ratemyprofessors.com).

> **Looking for TypeScript?** Check out the [TypeScript version](https://github.com/amaanjaved1/rate-my-professors-client-ts).

## Requirements

- **Python 3.10** or later
- Works with type checkers (Pydantic models, fully typed API)

## Installation

```bash
pip install ratemyprofessors-client
```

## Available Functions

Create a client and call any of these methods. See the [full docs](https://amaanjaved1.github.io/Rate-My-Professors-API-Client-Python/) for parameters, return types, and examples.

```python
from rmp_client import RMPClient

with RMPClient() as client:
    ...
```

**Schools**

- `search_schools(query)` — Search schools by name. Returns paginated results.
- `get_school(school_id)` — Get a single school by its numeric ID.
- `get_compare_schools(school_id_1, school_id_2)` — Fetch two schools side by side.
- `get_school_ratings_page(school_id)` — Get one page of school ratings (cached after first fetch).
- `iter_school_ratings(school_id)` — Iterator over all ratings for a school.

**Professors**

- `search_professors(query)` — Search professors by name. Returns paginated results.
- `list_professors_for_school(school_id)` — List professors at a given school.
- `iter_professors_for_school(school_id)` — Iterator over all professors at a school.
- `get_professor(professor_id)` — Get a single professor by their numeric ID.
- `get_professor_ratings_page(professor_id)` — Get one page of professor ratings (cached after first fetch).
- `iter_professor_ratings(professor_id)` — Iterator over all ratings for a professor.

**Low-level**

- `raw_query(payload)` — Send a raw GraphQL payload to the RMP endpoint.

**Lifecycle**

- `close()` — Close the client and clear caches. Safe to call multiple times.

## Errors and What They Mean

All errors extend `RMPError`. Catch and narrow with `isinstance`:

- **`HttpError`** — The server returned a non-2xx status code (e.g. 404, 500).
- **`ParsingError`** — The response couldn't be parsed (e.g. professor/school not found).
- **`RateLimitError`** — The client's local rate limiter blocked the request.
- **`RetryError`** — The request failed after all retry attempts. Contains the last underlying error.
- **`RMPAPIError`** — The GraphQL API returned an `errors` array in the response.
- **`ConfigurationError`** — Invalid client configuration.

```python
from rmp_client import RMPClient, HttpError, ParsingError

with RMPClient() as client:
    try:
        prof = client.get_professor("2823076")
    except ParsingError:
        print("Professor not found")
    except HttpError as e:
        print(f"HTTP error: {e.status_code}")
```

## Types

All methods return Pydantic models. Import any of these:

```python
from rmp_client.models import (
    School,
    Professor,
    Rating,
    SchoolRating,
    ProfessorSearchResult,
    SchoolSearchResult,
    ProfessorRatingsPage,
    SchoolRatingsPage,
    CompareSchoolsResult,
)
```

- **`School`** — ID, name, location, overall quality, category ratings (reputation, safety, etc.)
- **`Professor`** — ID, name, department, school, overall rating, difficulty, percent take again
- **`Rating`** — Date, comment, quality, difficulty, tags, course, thumbs up/down
- **`SchoolRating`** — Date, comment, overall score, category ratings, thumbs up/down
- **`ProfessorSearchResult`** / **`SchoolSearchResult`** — Paginated list with `has_next_page` and `next_cursor`
- **`ProfessorRatingsPage`** / **`SchoolRatingsPage`** — One page of ratings with cursor pagination
- **`CompareSchoolsResult`** — A pair of schools

## Extras

Optional helpers for data pipelines:

```python
from rmp_client import (
    analyze_sentiment,
    normalize_comment,
    is_valid_comment,
    build_course_mapping,
    clean_course_label,
)
```

- `normalize_comment(text, *, strip_html=True, strip_punctuation=False)` — Normalize text for deduplication (trim, strip HTML, lowercase, collapse whitespace; optionally strip punctuation)
- `is_valid_comment(text, *, min_len=10)` — Validate a comment and return a `ValidationResult` with diagnostics (empty, too short, all caps, excessive repeats, no alpha)
- `clean_course_label(raw)` — Clean scraped course labels (remove counts, normalize whitespace)
- `build_course_mapping(scraped, valid)` — Map scraped labels to known course codes
- `analyze_sentiment(text)` — Compute sentiment label from text (uses TextBlob)
