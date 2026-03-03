### Extras for Ingestion Pipelines

These helpers are optional and live under `rmp_client.extras`.

Install with:

```bash
pip install 'ratemyprofessors-client[sentiment]'
```

#### Sentiment

```python
from rmp_client.extras.sentiment import analyze_sentiment

result = analyze_sentiment("Great prof, explains concepts clearly.")
print(result.score, result.label)
```

#### Dedupe helpers

```python
from rmp_client.extras.dedupe import normalize_comment, is_valid_comment

raw = "  This prof is AMAZING!!!  "
normalized = normalize_comment(raw)
if is_valid_comment(normalized):
    ...
```

#### Course code helpers

```python
from rmp_client.extras.course_codes import build_course_mapping

scraped = ["ANAT 215 (12)", "phys115"]
valid = ["ANAT 215", "PHYS 115"]

mapping = build_course_mapping(scraped, valid)
```

