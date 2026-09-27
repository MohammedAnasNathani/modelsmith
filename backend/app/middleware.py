from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

log = logging.getLogger("modelsmith.access")

_STRICT_PREFIXES = (
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/password",
)
GENERAL_LIMIT = 600
GENERAL_WINDOW = 60.0
STRICT_LIMIT = 20
STRICT_WINDOW = 60.0

class _SlidingWindow:

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock_last_prune = 0.0

    def allow(self, key: str, limit: int, window: float) -> tuple[bool, float]:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = window - (now - bucket[0])
            return False, max(0.2, retry_after)
        bucket.append(now)
        self._maybe_prune(now)
        return True, 0.0

    def remaining(self, key: str, limit: int, window: float) -> int:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        return max(0, limit - len(bucket))

    def allow_peek(self, key: str, limit: int, window: float) -> tuple[bool, float]:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False, max(0.2, window - (now - bucket[0]))
        return True, 0.0

    def record(self, key: str) -> None:
        self._hits[key].append(time.monotonic())

    def _maybe_prune(self, now: float) -> None:
        if now - self._lock_last_prune < 300:
            return
        self._lock_last_prune = now
        stale = [k for k, v in self._hits.items()
                 if not v or v[-1] <= now - 600]
        for k in stale:
            del self._hits[k]

class RateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        path = request.url.path
        strict = any(path.startswith(p) for p in _STRICT_PREFIXES)

        if strict:
            ok, retry_after = _WINDOW.allow_peek("s:" + client, STRICT_LIMIT, STRICT_WINDOW)
            if not ok:
                log.warning("rate limited %s on %s", client, path)
                return JSONResponse(
                    {"detail": "Too many failed attempts. Try again shortly."},
                    status_code=429,
                    headers={"Retry-After": str(int(retry_after) + 1)},
                )
            response = await call_next(request)
            if response.status_code in (400, 401, 403, 422):
                _WINDOW.record("s:" + client)
            return response

        ok, retry_after = _WINDOW.allow("g:" + client, GENERAL_LIMIT, GENERAL_WINDOW)
        if not ok:
            log.warning("rate limited %s on %s", client, path)
            return JSONResponse(
                {"detail": "Too many requests. Slow down and try again shortly."},
                status_code=429,
                headers={"Retry-After": str(int(retry_after) + 1),
                         "X-RateLimit-Remaining": "0"},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(
            _WINDOW.remaining("g:" + client, GENERAL_LIMIT, GENERAL_WINDOW))
        return response

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/assets"):
            return await call_next(request)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            ms = (time.perf_counter() - start) * 1000
            client = request.client.host if request.client else "-"
            rid = getattr(request.state, "request_id", "")
            log.info("%s %s -> %s %.1fms (%s)%s",
                     request.method, request.url.path, status, ms, client,
                     f" rid={rid}" if rid else "")

class RequestIDMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        import uuid
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

class AssetCacheMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/") and response.status_code == 200:
            response.headers.setdefault("Cache-Control", "public, max-age=604800, immutable")
        return response

_WINDOW = _SlidingWindow()
