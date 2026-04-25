"""Tests for TokenBucket rate limiter."""

from __future__ import annotations

import time

from rmp_client.rate_limit import TokenBucket


class TestTokenBucketConsume:
    def test_consumes_without_error(self) -> None:
        bucket = TokenBucket(capacity=10, refill_per_second=10)
        for _ in range(5):
            bucket.consume()

    def test_refill_over_time(self) -> None:
        bucket = TokenBucket(capacity=2, refill_per_second=10.0)
        bucket.consume()
        bucket.consume()
        time.sleep(0.25)
        start = time.monotonic()
        bucket.consume()
        bucket.consume()
        assert time.monotonic() - start < 0.1

    def test_consume_amount(self) -> None:
        bucket = TokenBucket(capacity=10, refill_per_second=100.0)
        bucket.consume(amount=5.0)
        bucket.consume(amount=5.0)
        time.sleep(0.15)
        bucket.consume(amount=10.0)
