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


class TestReminderAdjustAPI:
    """Integration tests for the /api/<reminder_id>/adjust endpoint."""

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.reminders.analytics.track_event')
    @patch('app.routes.reminders.reminder_service.adjust_reminder_by_days')
    def test_api_adjust_postpone(self, mock_adjust, mock_analytics, mock_auth, app):
        """Should postpone reminder via API when authenticated."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock service function to return success
        mock_adjust.return_value = (True, None)

        # Make API request
        response = client.post(
            '/reminders/api/12345678-1234-1234-1234-123456789012/adjust',
            json={"days": 2},
            headers={'Content-Type': 'application/json'}
        )

        # Assertions
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'postponed by 2 day' in data['message']

        # Verify service was called correctly
        mock_adjust.assert_called_once_with(
            '12345678-1234-1234-1234-123456789012',
            'test-user-id',
            2
        )

        # Verify analytics tracking
        assert mock_analytics.called

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.reminders.analytics.track_event')
    @patch('app.routes.reminders.reminder_service.adjust_reminder_by_days')
    def test_api_adjust_advance(self, mock_adjust, mock_analytics, mock_auth, app):
        """Should advance reminder via API with negative days."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock service function to return success
        mock_adjust.return_value = (True, None)

        # Make API request with negative days
        response = client.post(
            '/reminders/api/12345678-1234-1234-1234-123456789012/adjust',
            json={"days": -1},
            headers={'Content-Type': 'application/json'}
        )

        # Assertions
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'advanced by 1 day' in data['message']

        # Verify service was called with negative days
        mock_adjust.assert_called_once_with(
            '12345678-1234-1234-1234-123456789012',
            'test-user-id',
            -1
        )

    @patch('app.utils.auth.get_current_user')
    def test_api_adjust_validates_days(self, mock_auth, app):
        """Should validate days parameter."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Test days > 30
        response = client.post(
            '/reminders/api/12345678-1234-1234-1234-123456789012/adjust',
            json={"days": 31},
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code == 400
        assert 'between -7 and +30' in response.get_json()['error']

        # Test days < -7
        response = client.post(
            '/reminders/api/12345678-1234-1234-1234-123456789012/adjust',
            json={"days": -8},
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code == 400
        assert 'between -7 and +30' in response.get_json()['error']

        # Test days = 0
        response = client.post(
            '/reminders/api/12345678-1234-1234-1234-123456789012/adjust',
            json={"days": 0},
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code == 400
        assert 'Cannot adjust by 0 days' in response.get_json()['error']

        # Test missing days parameter
        response = client.post(
            '/reminders/api/12345678-1234-1234-1234-123456789012/adjust',
            json={},
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code == 400
        assert 'Missing' in response.get_json()['error']

        # Test invalid days type
        response = client.post(
            '/reminders/api/12345678-1234-1234-1234-123456789012/adjust',
            json={"days": "not-a-number"},
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code == 400
        assert 'Invalid' in response.get_json()['error']

    def test_api_adjust_requires_auth(self, app):
        """Should require authentication."""
        client = app.test_client()

        # Make request without authentication
        response = client.post(
            '/reminders/api/12345678-1234-1234-1234-123456789012/adjust',
            json={"days": 2},
            headers={'Content-Type': 'application/json'}
        )

        # Should redirect or return 401/403
        assert response.status_code in [302, 308, 401, 403]

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.reminders.reminder_service.adjust_reminder_by_days')
    def test_api_adjust_validates_uuid(self, mock_adjust, mock_auth, app):
        """Should validate reminder ID format."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Test invalid UUID format
        response = client.post(
            '/reminders/api/invalid-uuid/adjust',
            json={"days": 2},
            headers={'Content-Type': 'application/json'}
        )

        assert response.status_code == 400
        assert 'Invalid reminder ID' in response.get_json()['error']

        # Verify service was not called
        mock_adjust.assert_not_called()
