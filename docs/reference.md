### API Reference

#### RMPClient

The main entry point. Use as a context manager or call `close()` when done.

```python
from rmp_client import RMPClient, RMPClientConfig

with RMPClient(config=RMPClientConfig()) as client:
    ...
```

**School methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `search_schools(query, *, page_size=20, cursor=None)` | `SchoolSearchResult` | Search schools by name |
| `get_school(school_id)` | `School` | Fetch a single school with category ratings |
| `get_compare_schools(school_id_1, school_id_2)` | `CompareSchoolsResult` | Fetch two schools side by side |
| `get_school_ratings_page(school_id, *, cursor=None, page_size=20)` | `SchoolRatingsPage` | Get one page of school ratings (cached) |
| `iter_school_ratings(school_id, *, page_size=20, since=None)` | `Iterator[SchoolRating]` | Iterate all school ratings |

**Professor methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `search_professors(query, *, school_id=None, page_size=20, cursor=None)` | `ProfessorSearchResult` | Search professors by name |
| `list_professors_for_school(school_id, *, query=None, page_size=20, cursor=None)` | `ProfessorSearchResult` | List professors at a school |
| `iter_professors_for_school(school_id, *, query=None, page_size=20)` | `Iterator[Professor]` | Iterate all professors at a school |
| `get_professor(professor_id)` | `Professor` | Fetch a single professor |
| `get_professor_ratings_page(professor_id, *, cursor=None, page_size=20, course_filter=None)` | `ProfessorRatingsPage` | Get one page of professor ratings (cached) |
| `iter_professor_ratings(professor_id, *, page_size=20, since=None, course_filter=None)` | `Iterator[Rating]` | Iterate all professor ratings |

**Low-level:**

| Method | Returns | Description |
|--------|---------|-------------|
| `raw_query(payload)` | `dict` | Send a raw GraphQL payload |
| `close()` | `None` | Close the HTTP client and clear caches |

---

#### Models

All models are Pydantic `BaseModel` subclasses.

**`School`** — `id`, `name`, `location`, `overall_quality`, `num_ratings`, `reputation`, `safety`, `happiness`, `facilities`, `social`, `location_rating`, `clubs`, `opportunities`, `internet`, `food`

**`Professor`** — `id`, `name`, `department`, `school` (School), `url`, `overall_rating`, `num_ratings`, `percent_take_again`, `level_of_difficulty`, `tags`, `rating_distribution`

**`Rating`** — `date`, `comment`, `quality`, `difficulty`, `tags`, `course_raw`, `details`, `thumbs_up`, `thumbs_down`

**`SchoolRating`** — `date`, `comment`, `overall`, `category_ratings` (dict), `thumbs_up`, `thumbs_down`

**`ProfessorSearchResult`** — `professors`, `total`, `page_size`, `has_next_page`, `next_cursor`

**`SchoolSearchResult`** — `schools`, `total`, `page_size`, `has_next_page`, `next_cursor`

**`ProfessorRatingsPage`** — `professor`, `ratings`, `has_next_page`, `next_cursor`

**`SchoolRatingsPage`** — `school`, `ratings`, `has_next_page`, `next_cursor`

**`CompareSchoolsResult`** — `school_1`, `school_2`

---

#### Errors

All errors extend `RMPError`.

| Error | Description |
|-------|-------------|
| `HttpError` | Non-2xx HTTP response. Has `status_code`, `url`, `body`. |
| `ParsingError` | Could not parse the GraphQL response (e.g. entity not found). |
| `RateLimitError` | Local rate limiter blocked the request. |
| `RetryError` | All retry attempts exhausted. Wraps the last exception. |
| `RMPAPIError` | GraphQL API returned an `errors` array. Has `details`. |
| `ConfigurationError` | Invalid client configuration. |

```python
from rmp_client import RMPClient, HttpError, ParsingError

with RMPClient() as client:
    try:
        prof = client.get_professor("999999")
    except ParsingError:
        print("Professor not found")
    except HttpError as e:
        print(f"HTTP {e.status_code}")
```
