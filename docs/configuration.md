### Configuration

The client is configured via `RMPClientConfig` and environment variables.

```python
from rmp_client import RMPClientConfig, RMPClient

config = RMPClientConfig(
    base_url="https://www.ratemyprofessors.com/graphql",
    timeout_seconds=10.0,
    max_retries=3,
    rate_limit_per_minute=60,
)

client = RMPClient(config)
```

Environment variables (optional):

- `RMP_CLIENT_BASE_URL`
- `RMP_CLIENT_TIMEOUT_SECONDS`
- `RMP_CLIENT_MAX_RETRIES`
- `RMP_CLIENT_RATE_LIMIT_PER_MINUTE`

