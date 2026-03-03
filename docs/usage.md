### Usage

#### Basic client

```python
from rmp_client import RMPClient

with RMPClient() as client:
    result = client.search_professors("Smith", page_size=10)
    for prof in result.professors:
        print(prof.name, prof.overall_rating)
```

#### Iterate professors for a school

```python
from rmp_client import RMPClient

SCHOOL_ID = 1466  # Queen's University at Kingston, for example

with RMPClient() as client:
    for prof in client.iter_professors_for_school(SCHOOL_ID, page_size=50):
        print(prof.name, prof.num_ratings)
```

#### Fetch professor details and ratings

```python
from datetime import date
from rmp_client import RMPClient

with RMPClient() as client:
    professor = client.get_professor("PROFESSOR_ID")

    for rating in client.iter_professor_ratings(professor.id, since=date(2024, 1, 1)):
        print(rating.date, rating.quality, rating.comment)
```

