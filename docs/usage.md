### Usage

All examples use the `RMPClient` context manager, which handles connection setup and teardown.

#### Search schools

```python
from rmp_client import RMPClient

with RMPClient() as client:
    result = client.search_schools("queens")
    for school in result.schools:
        print(school.name, school.location, school.overall_quality)

    # Cursor pagination
    if result.has_next_page:
        page2 = client.search_schools("queens", cursor=result.next_cursor)
```

#### Get a school by ID

```python
with RMPClient() as client:
    school = client.get_school("1466")
    print(school.name, school.location, school.overall_quality)
    print(f"Reputation: {school.reputation}, Safety: {school.safety}")
```

#### Compare two schools

```python
with RMPClient() as client:
    result = client.get_compare_schools("1466", "1491")
    print(result.school_1.name, "vs", result.school_2.name)
```

#### Search professors

```python
with RMPClient() as client:
    result = client.search_professors("Smith")
    for prof in result.professors:
        print(prof.name, prof.overall_rating, prof.school.name if prof.school else "")

    # Filter by school
    result = client.search_professors("Smith", school_id="1530")
```

#### List professors at a school

```python
with RMPClient() as client:
    result = client.list_professors_for_school(1466, page_size=20)
    for prof in result.professors:
        print(prof.name, prof.department)
```

#### Iterate all professors at a school

```python
with RMPClient() as client:
    for prof in client.iter_professors_for_school(1466, page_size=50):
        print(prof.name, prof.num_ratings)
```

#### Get a professor by ID

```python
with RMPClient() as client:
    prof = client.get_professor("2823076")
    print(prof.name, prof.department, prof.overall_rating)
    print(f"Difficulty: {prof.level_of_difficulty}")
    print(f"Would take again: {prof.percent_take_again}%")
```

#### Fetch professor ratings (paginated, cached)

```python
with RMPClient() as client:
    page = client.get_professor_ratings_page("2823076", page_size=10)
    print(f"Professor: {page.professor.name}")
    for rating in page.ratings:
        print(rating.date, rating.quality, rating.comment[:50])

    # Load more (served from cache, no extra network request)
    if page.has_next_page:
        page2 = client.get_professor_ratings_page("2823076", cursor=page.next_cursor)
```

#### Iterate all professor ratings

```python
from datetime import date
from rmp_client import RMPClient

with RMPClient() as client:
    for rating in client.iter_professor_ratings("2823076", since=date(2024, 1, 1)):
        print(rating.date, rating.quality, rating.comment)
```

#### Fetch school ratings (paginated, cached)

```python
with RMPClient() as client:
    page = client.get_school_ratings_page("1466", page_size=10)
    for rating in page.ratings:
        print(rating.date, rating.overall, rating.category_ratings)
```

#### Iterate all school ratings

```python
with RMPClient() as client:
    for rating in client.iter_school_ratings("1466"):
        print(rating.date, rating.overall, rating.comment[:50])
```

#### Send a raw GraphQL query

```python
with RMPClient() as client:
    data = client.raw_query({
        "query": "query { viewer { id } }",
        "variables": {},
    })
    print(data)
```
