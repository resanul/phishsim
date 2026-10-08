"""Simple in-process sliding-window rate limiter.

For a single-process deployment this is sufficient; for multi-worker/
multi-node production deployments, back this with Redis instead (swap the
in-memory dict for INCR+EXPIRE against settings.redis_url).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

_hits: dict[str, deque] = defaultdict(deque)


def is_rate_limited(key: str, max_requests: int, window_seconds: int) -> bool:
    now = time.monotonic()
    bucket = _hits[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= max_requests:
        return True
    bucket.append(now)
    return False
