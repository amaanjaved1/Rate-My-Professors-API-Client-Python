### RateMyProfessors API Client

An unofficial, typed Python client for [RateMyProfessors](https://www.ratemyprofessors.com).

All data is fetched via RMP's GraphQL API -- no HTML scraping or browser automation required.

**Features:**

- Strong typing via Pydantic models
- Automatic retries with configurable max attempts
- Token-bucket rate limiting (default 60 req/min)
- In-memory caching for ratings pages (pre-fetches all ratings on first load)
- Cursor-based pagination for all list/search endpoints
- Clear error hierarchy for precise exception handling
- Built-in helpers for ingestion workflows (sentiment, dedupe, course codes)

**Quick start:**

```python
from rmp_client import RMPClient

with RMPClient() as client:
    prof = client.get_professor("2823076")
    print(prof.name, prof.overall_rating)

    for rating in client.iter_professor_ratings(prof.id):
        print(rating.date, rating.quality, rating.comment)
```

**Documentation:**

- [Usage](usage.md) — Quickstart examples for every endpoint
- [Configuration](configuration.md) — Tuning retries, rate limits, timeouts, and headers
- [API Reference](reference.md) — Full method and type reference
- [Extras](extras.md) — Ingestion helpers (sentiment, dedupe, course mapping)
