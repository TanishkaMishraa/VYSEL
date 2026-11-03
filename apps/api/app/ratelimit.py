"""Fixed-window rate limiting in Redis.

Fails open: if Redis is unreachable, requests are allowed and a warning is logged
(availability over strictness for a dev-stage product; revisit before launch).
"""

import logging
from functools import lru_cache

import redis
from fastapi import Request

from app.config import get_settings
from app.errors import ApiError

log = logging.getLogger(__name__)


@lru_cache
def _client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce(bucket: str, key: str, limit: int, window_seconds: int) -> None:
    """Raise 429 once `key` exceeds `limit` hits within the window."""
    if not get_settings().rate_limit_enabled:
        return
    redis_key = f"vysel:rl:{bucket}:{key}"
    try:
        pipe = _client().pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds, nx=True)
        count, _ = pipe.execute()
        ttl = _client().ttl(redis_key)
    except redis.RedisError as exc:
        log.warning("rate limiter unavailable, allowing request: %s", exc)
        return
    if count > limit:
        raise ApiError(429, "RATE_LIMITED", f"Too many attempts. Try again in {max(ttl, 1)} seconds.", retry_after=max(ttl, 1))
