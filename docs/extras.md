### Helpers for Ingestion Pipelines

These helpers are part of the main package. Import them from `rmp_client`:

```python
from rmp_client import (
    analyze_sentiment,
    normalize_comment,
    is_valid_comment,
    build_course_mapping,
    clean_course_label,
)
```

#### Sentiment

```python
result = analyze_sentiment("Great prof, explains concepts clearly.")
print(result.score, result.label)
```

#### Dedupe helpers

```python
raw = "  This prof is AMAZING!!!  "
normalized = normalize_comment(raw)
if is_valid_comment(normalized):
    ...
```

#### Course code helpers

```python
scraped = ["ANAT 215 (12)", "phys115"]
valid = ["ANAT 215", "PHYS 115"]

mapping = build_course_mapping(scraped, valid)
cleaned = clean_course_label("MATH 101 (5)")
```
