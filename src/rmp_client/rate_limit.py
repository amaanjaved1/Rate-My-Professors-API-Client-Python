from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    capacity: int
    refill_per_second: float

    def __post_init__(self) -> None:
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_second)

    def consume(self, amount: float = 1.0) -> None:
        """Consume tokens from the bucket, blocking until available."""
        with self._lock:
            while True:
                self._refill()
                if self._tokens >= amount:
                    self._tokens -= amount
                    return
                needed = amount - self._tokens
                sleep_for = max(needed / self.refill_per_second, 0.01)
                time.sleep(sleep_for)

