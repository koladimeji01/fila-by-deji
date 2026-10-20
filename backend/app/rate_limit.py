"""Basic route-scoped abuse protection.

Production counters are shared across API workers through Redis. Development and
unit tests use a process-local counter and MUST NOT use this mode in production.
IP-based limits are an initial defense, not account lockout or bot mitigation.
"""
from functools import lru_cache
from hashlib import sha256
from threading import Lock
import time

import anyio
from fastapi import Request
from fastapi.responses import JSONResponse

from .config import get_settings

# Number of requests permitted per source address inside a fixed time window.
RULES = {
    'login': (10, 300),
    'register': (5, 3600),
    'draft': (20, 60),
    'reserve': (15, 60),
    'admin-write': (30, 60),
}

_redis_script = """
local number = redis.call('INCR', KEYS[1])
if number == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return number
"""
_guard = Lock()
_memory: dict[tuple[str, str, int], int] = {}


def match_rule(method: str, path: str) -> str | None:
    if method == 'POST':
        if path == '/api/v1/auth/login':
            return 'login'
        if path == '/api/v1/auth/register':
            return 'register'
        if path == '/api/v1/orders/drafts':
            return 'draft'
        if path.startswith('/api/v1/orders/') and path.endswith('/reserve'):
            return 'reserve'
        if path.startswith('/api/v1/admin/'):
            return 'admin-write'
    if method == 'PUT' and path.startswith('/api/v1/admin/'):
        return 'admin-write'
    return None


@lru_cache(maxsize=2)
def redis_client(url: str):
    from redis import Redis  # installed by requirements.txt; lazy for local dev
    return Redis.from_url(url, socket_timeout=3, socket_connect_timeout=3,
                          decode_responses=True)


def _redis_increment(url: str, key: str, ttl: int) -> int:
    return int(redis_client(url).eval(_redis_script, 1, key, ttl))


def _local_increment(rule: str, identity: str, bucket: int) -> int:
    with _guard:
        # Bound memory growth, for development/test only. Expired buckets are stale.
        if len(_memory) >= 5000:
            _memory.clear()
        key = (rule, identity, bucket)
        _memory[key] = _memory.get(key, 0) + 1
        return _memory[key]


async def limit_request(request: Request, call_next):
    """HTTP middleware; fail closed on Redis errors in production."""
    rule = match_rule(request.method, request.url.path)
    if rule is not None:
        maximum, seconds = RULES[rule]
        now = int(time.time())
        bucket = now // seconds
        wait = seconds - (now % seconds)
        source = request.client.host if request.client else 'unknown'
        # Avoid storing raw IP addresses inside Redis keys.
        identity = sha256(source.encode('utf-8')).hexdigest()
        settings = get_settings()
        if settings.app_env == 'production':
            try:
                key = f'fila:rl:{rule}:{identity}:{bucket}'
                count = await anyio.to_thread.run_sync(
                    _redis_increment, settings.rate_limit_redis_url, key, seconds + 2)
            except Exception:
                # Do not allow unlimited login attempts when Redis is down.
                return JSONResponse(status_code=503, content={'detail':'Security service temporarily unavailable'},
                                    headers={'Cache-Control':'no-store','Retry-After':'30'})
        else:
            count = _local_increment(rule, identity, bucket)
        if count > maximum:
            return JSONResponse(status_code=429, content={'detail':'Too many requests. Please try again later.'},
                                headers={'Retry-After':str(wait),'Cache-Control':'no-store'})
    return await call_next(request)
