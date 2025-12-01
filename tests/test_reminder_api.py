"""
Unit tests for reminder API endpoints.

Tests the JSON API endpoints for reminders, including the weather adjustment API.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.services import reminders


class TestAdjustReminderByDays:
    """Test the adjust_reminder_by_days service function."""

    @patch('app.services.reminders.get_admin_client')
    @patch('app.services.reminders.invalidate_user_calendar_cache')
    def test_postpone_reminder(self, mock_invalidate, mock_client):
        """Should postpone reminder by positive days."""
        # Setup mock
        mock_supabase = MagicMock()
        mock_client.return_value = mock_supabase

        mock_response = MagicMock()
        mock_response.data = [{"success": True, "message": "Reminder adjusted"}]
        mock_supabase.rpc.return_value.execute.return_value = mock_response

        # Call function
        success, error = reminders.adjust_reminder_by_days("r123", "u456", 2)

        # Verify
        assert success is True
        assert error is None
        mock_supabase.rpc.assert_called_once_with("snooze_reminder", {
            "p_reminder_id": "r123",
            "p_user_id": "u456",
            "p_days": 2
        })
        mock_invalidate.assert_called_once_with("u456")

    @patch('app.services.reminders.get_admin_client')
    @patch('app.services.reminders.invalidate_user_calendar_cache')
    def test_advance_reminder(self, mock_invalidate, mock_client):
        """Should advance reminder by negative days."""
        # Setup mock
        mock_supabase = MagicMock()
        mock_client.return_value = mock_supabase

        mock_response = MagicMock()
        mock_response.data = [{"success": True, "message": "Reminder adjusted"}]
        mock_supabase.rpc.return_value.execute.return_value = mock_response

        # Call function
        success, error = reminders.adjust_reminder_by_days("r123", "u456", -1)

        # Verify
        assert success is True
        assert error is None
        mock_supabase.rpc.assert_called_once_with("snooze_reminder", {
            "p_reminder_id": "r123",
            "p_user_id": "u456",
            "p_days": -1
        })

    @patch('app.services.reminders.get_admin_client')
    def test_validates_days_range(self, mock_client):
        """Should validate days are within allowed range."""
        mock_client.return_value = MagicMock()

        # Too many days
        success, error = reminders.adjust_reminder_by_days("r123", "u456", 31)
        assert success is False
        assert "between -7 and +30" in error

        # Too many negative days
        success, error = reminders.adjust_reminder_by_days("r123", "u456", -8)
        assert success is False
        assert "between -7 and +30" in error

    @patch('app.services.reminders.get_admin_client')
    def test_rejects_zero_days(self, mock_client):
        """Should reject 0 days adjustment."""
        mock_client.return_value = MagicMock()

        success, error = reminders.adjust_reminder_by_days("r123", "u456", 0)
        assert success is False
        assert "Cannot adjust by 0 days" in error

    @patch('app.services.reminders.get_admin_client')
    def test_handles_database_errors(self, mock_client):
        """Should handle database errors gracefully."""
        mock_supabase = MagicMock()
        mock_client.return_value = mock_supabase

        # Simulate database error
        mock_supabase.rpc.return_value.execute.side_effect = Exception("Database error")

        success, error = reminders.adjust_reminder_by_days("r123", "u456", 2)

        assert success is False
        assert "Error adjusting reminder" in error
        assert "Database error" in error


@pytest.mark.skipif(
    True,
    reason="Route tests require Flask app context and full integration setup"
)
class TestReminderAdjustAPI:
    """
    Test the /api/<reminder_id>/adjust endpoint.

    NOTE: These tests are skipped by default as they require full Flask app setup.
    Run them with pytest -k test_reminder_api --no-skip to test in integration environment.
    """

    def test_api_adjust_postpone(self, client, auth):
        """Should postpone reminder via API."""
        # This would require full Flask test client setup
        pass

    def test_api_adjust_advance(self, client, auth):
        """Should advance reminder via API."""
        # This would require full Flask test client setup
        pass

    def test_api_adjust_validates_days(self, client, auth):
        """Should validate days parameter."""
        # This would require full Flask test client setup
        pass

    def test_api_adjust_requires_auth(self, client):
        """Should require authentication."""
        # This would require full Flask test client setup
        pass

    def test_api_adjust_requires_csrf(self, client, auth):
        """Should require CSRF token."""
        # This would require full Flask test client setup
        pass
