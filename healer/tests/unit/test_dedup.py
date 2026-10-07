"""
Unit tests for the alert deduplication logic.
"""

from unittest.mock import patch, MagicMock
from healer.src.main import is_duplicate_alert


def test_dedup_disabled_when_window_zero():
    """When DEDUP_WINDOW_SECONDS is 0, dedup is skipped."""
    with patch("healer.src.main.settings") as mock_settings:
        mock_settings.DEDUP_WINDOW_SECONDS = 0
        assert is_duplicate_alert("HighMemoryUsage", "leaky_service") is False


def test_dedup_returns_false_when_no_prior_incident():
    """When no prior incident exists, dedup returns False."""
    with (
        patch("healer.src.main.settings") as mock_settings,
        patch("healer.src.main.get_db_connection") as mock_conn,
    ):
        mock_settings.DEDUP_WINDOW_SECONDS = 60
        cur = MagicMock()
        cur.fetchone.return_value = None
        mock_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = MagicMock()
        mock_conn.return_value.cursor.return_value.fetchone.return_value = None

        assert is_duplicate_alert("HighMemoryUsage", "leaky_service") is False


def test_dedup_returns_true_when_prior_incident_exists():
    """When a prior incident exists within the window, dedup returns True."""
    with (
        patch("healer.src.main.settings") as mock_settings,
        patch("healer.src.main.get_db_connection") as mock_conn,
    ):
        mock_settings.DEDUP_WINDOW_SECONDS = 60
        cur = MagicMock()
        cur.fetchone.return_value = (1,)
        mock_conn.return_value.cursor.return_value = cur

        assert is_duplicate_alert("HighMemoryUsage", "leaky_service") is True
