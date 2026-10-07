import time
from collections import defaultdict, deque
from threading import Lock
from typing import Dict, Deque

from fastapi import Request, HTTPException, status

from healer.src.config import settings


class SlidingWindowRateLimiter:
    """
    Simple in-memory sliding-window rate limiter keyed by client IP.
    """

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, client_ip: str) -> bool:
        now = time.time()
        with self._lock:
            for key in list(self._hits):
                if not self._hits[key] or self._hits[key][-1] <= now - self.window_seconds:
                    del self._hits[key]
            if client_ip not in self._hits and len(self._hits) >= 10000:
                return False
            dq = self._hits[client_ip]
            while dq and dq[0] <= now - self.window_seconds:
                dq.popleft()
            if len(dq) >= self.max_requests:
                return False
            dq.append(now)
            return True


_rate_limiter: SlidingWindowRateLimiter | None = None


def get_rate_limiter() -> SlidingWindowRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = SlidingWindowRateLimiter(max_requests=settings.RATE_LIMIT_PER_MINUTE)
    return _rate_limiter


def enforce_rate_limit(request: Request):
    """FastAPI dependency: raises 429 if the client has exceeded the rate limit."""
    limiter = get_rate_limiter()
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.check(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {settings.RATE_LIMIT_PER_MINUTE} requests per minute.",
        )
