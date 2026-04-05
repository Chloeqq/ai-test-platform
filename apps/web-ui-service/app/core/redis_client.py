from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import get_settings

LOGGER = logging.getLogger(__name__)

try:
    from redis import Redis
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover - keep local env resilient before deps refresh
    Redis = None  # type: ignore[assignment,misc]

    class RedisError(Exception):  # type: ignore[no-redef]
        pass


@lru_cache(maxsize=1)
def get_redis_client() -> Redis | None:
    settings = get_settings()
    if not settings.redis_enabled or Redis is None:
        return None
    try:
        return Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=2)
    except Exception as exc:
        LOGGER.warning("redis init failed: %s", exc)
        return None


def ping_redis() -> bool:
    client = get_redis_client()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except RedisError:
        return False
