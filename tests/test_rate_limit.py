"""Tests for TokenBucket rate limiter."""

from __future__ import annotations

import time

import pytest

from rmp_client.errors import RateLimitError
from rmp_client.rate_limit import TokenBucket


class TestTokenBucketConsume:
    """consume() with block=True (default)."""

    def test_consumes_without_error(self) -> None:
        bucket = TokenBucket(capacity=10, refill_per_second=10)
        for _ in range(5):
            bucket.consume()

    def test_exhausts_capacity_then_block_false_raises(self) -> None:
        bucket = TokenBucket(capacity=3, refill_per_second=1.0)
        for _ in range(3):
            bucket.consume()
        with pytest.raises(RateLimitError, match="rate limit"):
            bucket.consume(amount=1.0, block=False)

    def test_block_false_raises_when_insufficient_tokens(self) -> None:
        bucket = TokenBucket(capacity=1, refill_per_second=0.01)
        bucket.consume()  # exhaust
        with pytest.raises(RateLimitError):
            bucket.consume(block=False)

    def test_block_false_succeeds_when_tokens_available(self) -> None:
        bucket = TokenBucket(capacity=2, refill_per_second=10)
        bucket.consume(block=False)
        bucket.consume(block=False)

    def test_refill_over_time(self) -> None:
        bucket = TokenBucket(capacity=2, refill_per_second=10.0)  # refill 10 per second
        bucket.consume()
        bucket.consume()
        # After 0.2s we have 2 tokens again (0 + 10*0.2 = 2)
        time.sleep(0.25)
        bucket.consume(block=False)
        bucket.consume(block=False)

    def test_consume_amount(self) -> None:
        bucket = TokenBucket(capacity=10, refill_per_second=1.0)
        bucket.consume(amount=5.0)
        bucket.consume(amount=5.0)
        with pytest.raises(RateLimitError):
            bucket.consume(amount=1.0, block=False)
