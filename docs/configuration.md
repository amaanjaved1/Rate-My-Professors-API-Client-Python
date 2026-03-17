### Configuration

The client is configured via `RMPClientConfig`. All fields have sensible defaults.

```python
from rmp_client import RMPClientConfig, RMPClient

config = RMPClientConfig(
    base_url="https://www.ratemyprofessors.com/graphql",
    timeout_seconds=10.0,
    max_retries=3,
    rate_limit_per_minute=60,
)

with RMPClient(config) as client:
    ...
```

#### Available options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `base_url` | `str` | `https://www.ratemyprofessors.com/graphql` | GraphQL endpoint URL |
| `timeout_seconds` | `float` | `10.0` | HTTP request timeout |
| `max_retries` | `int` | `3` | Number of retry attempts for failed requests |
| `rate_limit_per_minute` | `int` | `60` | Max requests per minute (token bucket) |
| `user_agent` | `str` | Firefox UA | User-Agent header sent with every request |
| `default_headers` | `Mapping[str, str]` | UA + Accept-Language | Default headers for all requests |

#### Rate limiting

The client uses a token-bucket algorithm. Tokens replenish continuously at `rate_limit_per_minute / 60` tokens per second. Each request consumes one token. If no tokens are available, the request blocks until one becomes available.

```python
config = RMPClientConfig(rate_limit_per_minute=30)  # half the default rate
```

#### Retries

On 5xx errors or network failures, the client retries up to `max_retries` times. 4xx errors are **not** retried. After exhausting retries, a `RetryError` is raised containing the last underlying exception.

```python
config = RMPClientConfig(max_retries=5)  # more retries for flaky networks
```

#### Timeouts

The `timeout_seconds` value applies to each individual HTTP request (connect + read).

```python
config = RMPClientConfig(timeout_seconds=30.0)  # generous timeout
```
