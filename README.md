# RateMyProfessors API Client

Typed, retrying, rate-limited unofficial client for RateMyProfessors, with optional
helpers for ingestion workflows (sentiment, dedupe, course-code normalization).

> Note: This library is **unofficial** and may break if RMP changes their internal API.
> This library has been made open-source so that if/when there are any changes,
> someone is able to take note of these changes and help to contribute an update.

## Installation

```bash
pip install ratemyprofessors-client
```

With optional sentiment extras (TextBlob):

```bash
pip install 'ratemyprofessors-client[sentiment]'
```

## Quickstart

```python
from rmp_client import RMPClient

SCHOOL_ID = 1466  # example: Queen's University ID on RMP

with RMPClient() as client:
    for prof in client.iter_professors_for_school(SCHOOL_ID, page_size=20):
        print(prof.name, prof.overall_rating, prof.num_ratings)
```

Fetch details and iterate ratings incrementally:

```python
from datetime import date
from rmp_client import RMPClient

with RMPClient() as client:
    professor = client.get_professor("PROFESSOR_ID")

    for rating in client.iter_professor_ratings(professor.id, since=date(2024, 1, 1)):
        print(rating.date, rating.quality, rating.comment)
```

## How it works

### Package architecture

```mermaid
flowchart TB
    subgraph Your code
        User["Your script / app"]
    end

    subgraph rmp_client [rmp_client package]
        Client["RMPClient\n(client.py)"]
        Config["RMPClientConfig\n(config.py)"]
        Models["Models\n(School, Professor, Rating)\n(models.py)"]
        Errors["RMPError hierarchy\n(errors.py)"]
    end

    subgraph HTTP layer
        HttpCtx["HttpClientContext\n(http.py)"]
        Http["HttpClient\n(retries, headers)"]
        Bucket["TokenBucket\n(rate_limit.py)"]
    end

    subgraph External
        API["RMP GraphQL API\n(ratemyprofessors.com)"]
    end

    User --> Client
    Client --> Config
    Client --> HttpCtx
    HttpCtx --> Http
    Http --> Bucket
    Http --> API
    Client --> Models
    Client --> Errors
```

### Request flow

```mermaid
sequenceDiagram
    participant User
    participant RMPClient
    participant HttpClient
    participant TokenBucket
    participant httpx
    participant RMP API

    User->>RMPClient: e.g. get_professor(id) or iter_professors_for_school(school_id)
    RMPClient->>RMPClient: Build GraphQL-style payload
    RMPClient->>HttpClient: post_json(path, payload)
    HttpClient->>TokenBucket: consume()
    TokenBucket-->>HttpClient: (blocks until token available)
    HttpClient->>httpx: POST base_url, json=payload
    httpx->>RMP API: HTTPS request
    RMP API-->>httpx: JSON response
    httpx-->>HttpClient: response
    HttpClient->>HttpClient: Retry on 5xx / HTTP error
    HttpClient-->>RMPClient: dict (parsed JSON)
    RMPClient->>RMPClient: Parse into Professor / Rating / etc.
    RMPClient-->>User: Professor, Rating, or list
```

### Data models

```mermaid
erDiagram
    School ||--o{ Professor : "has"
    Professor ||--o{ Rating : "has"

    School {
        string id
        string name
        string city
        string state
        string country
    }

    Professor {
        string id
        string name
        string department
        float overall_rating
        int num_ratings
        School school
    }

    Rating {
        date date
        string comment
        float quality
        float difficulty
        string course_raw
    }

    ProfessorSearchResult {
        Professor[] professors
        int page
        int page_size
        bool has_next_page
    }

    ProfessorRatingsPage {
        Professor professor
        Rating[] ratings
        bool has_next_page
        string next_cursor
    }
```

### Extras and ingestion pipeline

```mermaid
flowchart LR
    subgraph RMPClient
        iter_professors["iter_professors_for_school"]
        iter_ratings["iter_professor_ratings"]
    end

    subgraph extras [rmp_client.extras]
        dedupe["dedupe\n(normalize_comment,\n is_valid_comment)"]
        sentiment["sentiment\n(analyze_sentiment)"]
        course_codes["course_codes\n(build_course_mapping)"]
    end

    subgraph Your pipeline [Your pipeline e.g. ingest_supabase]
        filter["Filter comments"]
        store["Supabase / DB"]
    end

    iter_professors --> iter_ratings
    iter_ratings --> filter
    filter --> dedupe
    dedupe --> sentiment
    iter_ratings --> course_codes
    sentiment --> store
    course_codes --> store
```

### CI/CD (publish to PyPI)

```mermaid
flowchart LR
    subgraph On any push
        T[Run tests\npytest]
    end

    subgraph On main push
        B[Build wheel + sdist]
        TestPyPI[Publish to TestPyPI]
    end

    subgraph On release published
        PyPI[Publish to PyPI]
    end

    T --> B
    B --> TestPyPI
    B --> PyPI
```

## Extras

Optional helpers live under `rmp_client.extras`:

- `rmp_client.extras.sentiment.analyze_sentiment`
- `rmp_client.extras.dedupe.normalize_comment` / `is_valid_comment`
- `rmp_client.extras.course_codes.build_course_mapping`

See `docs/` and `examples/` for more. This repo also includes an
`examples/ingest_supabase.py` script that mirrors a Supabase-centric
scraping pipeline using this client.

## Publishing to PyPI

This project follows the [Python Packaging User Guide](https://packaging.python.org/en/latest/overview/) and uses [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) with GitHub Actions.

1. **One-time setup**: On [pypi.org](https://pypi.org/manage/account/publishing/) add a trusted publisher for this repo (workflow `publish-to-pypi.yml`, environment `pypi`). Create a `pypi` environment in the repo and enable “Required reviewers” for production releases.
2. **Release**: Create and push a tag (e.g. `v0.1.0`). The workflow builds both a [wheel and an sdist](https://packaging.python.org/en/latest/overview/#python-binary-distributions) and publishes to PyPI. Any push builds and publishes to TestPyPI (use the `testpypi` environment).

Local build (no publish):

```bash
pip install build
python -m build
# Outputs in dist/: .whl (wheel) and .tar.gz (sdist)
```
