"""Simple in-memory sliding-window rate limiter (per IP). Sufficient for a
single-node deployment; swap for Redis in production."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:  # noqa: ANN001
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._window_seconds = 60.0
        self._limit = settings.rate_limit_per_minute

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        if request.url.path in ("/health", "/api/v1/health"):
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[client_ip]
            while bucket and now - bucket[0] > self._window_seconds:
                bucket.popleft()
            if len(bucket) >= self._limit:
                return JSONResponse(
                    status_code=429,
                    content={"success": False, "error": {"code": "RATE_LIMITED", "message": "Too many requests"}},
                )
            bucket.append(now)
        return await call_next(request)
