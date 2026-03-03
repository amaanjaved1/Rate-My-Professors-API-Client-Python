from rmp_client.rate_limit import TokenBucket


def test_token_bucket_consumes_without_error() -> None:
    bucket = TokenBucket(capacity=10, refill_per_second=10)
    for _ in range(5):
        bucket.consume()

