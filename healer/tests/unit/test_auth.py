"""
Unit tests for the API key authentication module.
"""

from unittest.mock import patch
from fastapi import HTTPException
from healer.src.auth import verify_api_key


def test_auth_skipped_when_no_key_set():
    """When HEALER_API_KEY is empty, auth is bypassed (local dev mode)."""
    from healer.src.config import settings

    with patch.object(settings, "HEALER_API_KEY", ""):
        result = verify_api_key(api_key="anything")
        assert result is None


def test_auth_passes_with_valid_key():
    from healer.src.config import settings

    with patch.object(settings, "HEALER_API_KEY", "secret-123"):
        result = verify_api_key(api_key="secret-123")
        assert result == "secret-123"


def test_auth_fails_with_invalid_key():
    from healer.src.config import settings

    with patch.object(settings, "HEALER_API_KEY", "secret-123"):
        try:
            verify_api_key(api_key="wrong-key")
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 401


def test_auth_fails_with_missing_key():
    from healer.src.config import settings

    with patch.object(settings, "HEALER_API_KEY", "secret-123"):
        try:
            verify_api_key(api_key=None)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 401
