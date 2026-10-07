"""
Unit tests for the rate limiter.
"""

from unittest.mock import patch, MagicMock
from healer.src.security.rate_limit import SlidingWindowRateLimiter, enforce_rate_limit


def test_rate_limiter_allows_under_limit():
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)
    for _ in range(5):
        assert limiter.check("192.168.1.1") is True


def test_rate_limiter_blocks_over_limit():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        assert limiter.check("10.0.0.1") is True
    assert limiter.check("10.0.0.1") is False


def test_rate_limiter_separate_clients():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
    assert limiter.check("client-a") is True
    assert limiter.check("client-b") is True
    assert limiter.check("client-a") is True
    assert limiter.check("client-b") is True
    assert limiter.check("client-a") is False


def test_enforce_rate_limit_raises_on_exceed():
    from fastapi import HTTPException

    request = MagicMock()
    request.client.host = "1.2.3.4"

    with patch("healer.src.security.rate_limit.settings") as mock_settings:
        mock_settings.RATE_LIMIT_PER_MINUTE = 1
        enforce_rate_limit(request)  # first request OK
        try:
            enforce_rate_limit(request)
            assert False, "Should have raised 429"
        except HTTPException as e:
            assert e.status_code == 429
