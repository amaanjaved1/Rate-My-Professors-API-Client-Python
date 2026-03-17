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

Compute a sentiment score and label from comment text (uses TextBlob internally).

```python
result = analyze_sentiment("Great prof, explains concepts clearly.")
print(result.score, result.label)  # e.g. 0.65 "positive"
```

#### Dedupe helpers

Normalize comments for deduplication and filter out low-quality entries.

```python
raw = "  This prof is AMAZING!!!  "
normalized = normalize_comment(raw)  # "this prof is amazing!!!"
if is_valid_comment(normalized, min_len=10):
    print("Valid comment")
```

#### Course code helpers

Map scraped RMP course labels to your course catalog.

```python
scraped = ["ANAT 215 (12)", "phys115"]
valid = ["ANAT 215", "PHYS 115"]

mapping = build_course_mapping(scraped, valid)
# {"ANAT 215 (12)": "ANAT 215", "phys115": "PHYS 115"}

cleaned = clean_course_label("MATH 101 (5)")
# "MATH 101"
```
