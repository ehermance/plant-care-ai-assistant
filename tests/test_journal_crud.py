"""
Unit and integration tests for Journal CRUD operations.

Tests journal entry deletion and API operations:
- Journal entry deletion with photo cleanup
- Quick log API endpoint
- Authorization and validation
"""

import pytest
from unittest.mock import patch


class TestJournalDelete:
    """Test journal entry delete operations."""

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.journal.journal_service.get_action_by_id')
    @patch('app.routes.journal.journal_service.delete_action')
    @patch('app.services.supabase_client.delete_plant_photo')
    def test_delete_journal_entry_success(
        self, mock_delete_photo, mock_delete, mock_get_action, mock_auth, app, sample_journal_entry
    ):
        """Should delete journal entry successfully."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock getting existing entry
        mock_get_action.return_value = sample_journal_entry

        # Mock successful deletion
        mock_delete.return_value = (True, None)

        # Make request
        response = client.post(
            '/journal/entry/action-123/delete',
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200
        assert b'deleted successfully' in response.data

        # Verify deletion was called
        mock_delete.assert_called_once_with('action-123', 'test-user-id')

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.journal.journal_service.get_action_by_id')
    @patch('app.routes.journal.journal_service.delete_action')
    @patch('app.routes.journal.delete_plant_photo')
    def test_delete_journal_entry_with_photo(
        self, mock_delete_photo, mock_delete, mock_get_action, mock_auth, app, sample_journal_entry
    ):
        """Should delete journal entry photos when deleting entry."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock existing entry with photos
        entry_with_photo = {
            **sample_journal_entry,
            'photo_url': 'https://storage.example.com/plant-photos/user123/photo.jpg',
            'photo_url_thumb': 'https://storage.example.com/plant-photos/user123/photo-thumb.jpg'
        }
        mock_get_action.return_value = entry_with_photo

        # Mock photo deletion to prevent real storage calls
        mock_delete_photo.return_value = True

        # Mock successful deletion
        mock_delete.return_value = (True, None)

        # Make request
        response = client.post(
            '/journal/entry/action-123/delete',
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200

        # Verify photos were deleted before entry deletion (2 calls: display + thumbnail)
        assert mock_delete_photo.call_count >= 2

        # Verify entry deletion was called
        mock_delete.assert_called_once()

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.journal.journal_service.get_action_by_id')
    def test_delete_journal_entry_validates_ownership(self, mock_get_action, mock_auth, app):
        """Should reject deletion when entry not found or doesn't belong to user."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock entry not found
        mock_get_action.return_value = None

        # Make request
        response = client.post(
            '/journal/entry/action-123/delete',
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200
        assert b'not found' in response.data

    def test_delete_journal_entry_requires_auth(self, app):
        """Should require authentication to delete journal entry."""
        client = app.test_client()

        # Make request without authentication
        response = client.post(
            '/journal/entry/action-123/delete',
            follow_redirects=False
        )

        # Should redirect to login
        assert response.status_code in [302, 308, 401, 403]

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.journal.journal_service.get_action_by_id')
    @patch('app.routes.journal.journal_service.delete_action')
    @patch('app.services.supabase_client.delete_plant_photo')
    def test_delete_journal_entry_handles_deletion_failure(
        self, mock_delete_photo, mock_delete, mock_get_action, mock_auth, app, sample_journal_entry
    ):
        """Should handle gracefully when deletion operation fails."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock getting existing entry
        mock_get_action.return_value = sample_journal_entry

        # Mock deletion failure
        mock_delete.return_value = (False, "Database error")

        # Make request
        response = client.post(
            '/journal/entry/action-123/delete',
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200
        assert b'Error deleting entry' in response.data


class TestJournalQuickLogAPI:
    """Test the quick log API endpoint for AJAX journal entries."""

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.journal.get_plant_by_id')
    @patch('app.routes.journal.journal_service.create_plant_action')
    def test_quick_log_water_success(self, mock_create, mock_get_plant, mock_auth, app, sample_plant):
        """Should create water journal entry via API."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock plant exists
        mock_get_plant.return_value = sample_plant

        # Mock successful creation
        mock_create.return_value = (
            {
                'id': 'action-123',
                'action_type': 'water',
                'plant_id': 'plant-123',
                'user_id': 'test-user-id'
            },
            None
        )

        # Make API request
        response = client.post(
            '/journal/api/quick-log',
            json={
                'plant_id': 'plant-123',
                'action_type': 'water',
                'amount_ml': 500
            },
            headers={'Content-Type': 'application/json'}
        )

        # Assertions
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'Water' in data['message']

        # Verify creation was called
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args[1]['action_type'] == 'water'
        assert call_args[1]['amount_ml'] == 500

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.journal.get_plant_by_id')
    @patch('app.routes.journal.journal_service.create_plant_action')
    def test_quick_log_fertilize_with_notes(self, mock_create, mock_get_plant, mock_auth, app, sample_plant):
        """Should create fertilize entry with notes via API."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock plant exists
        mock_get_plant.return_value = sample_plant

        # Mock successful creation
        mock_create.return_value = (
            {
                'id': 'action-456',
                'action_type': 'fertilize',
                'plant_id': 'plant-123',
                'notes': 'Added liquid fertilizer'
            },
            None
        )

        # Make API request
        response = client.post(
            '/journal/api/quick-log',
            json={
                'plant_id': 'plant-123',
                'action_type': 'fertilize',
                'notes': 'Added liquid fertilizer',
                'amount_ml': 50
            },
            headers={'Content-Type': 'application/json'}
        )

        # Assertions
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('app.utils.auth.get_current_user')
    def test_quick_log_validates_required_fields(self, mock_auth, app):
        """Should validate required fields in quick log request."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Make API request without required fields
        response = client.post(
            '/journal/api/quick-log',
            json={
                'plant_id': 'plant-123'
                # Missing action_type
            },
            headers={'Content-Type': 'application/json'}
        )

        # Assertions
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'required' in data['error'].lower()

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.journal.get_plant_by_id')
    def test_quick_log_validates_plant_ownership(self, mock_get_plant, mock_auth, app):
        """Should verify plant ownership before creating entry."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock plant not found (doesn't belong to user)
        mock_get_plant.return_value = None

        # Make API request
        response = client.post(
            '/journal/api/quick-log',
            json={
                'plant_id': 'plant-123',
                'action_type': 'water'
            },
            headers={'Content-Type': 'application/json'}
        )

        # Assertions
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'not found' in data['error'].lower()

    def test_quick_log_requires_auth(self, app):
        """Should require authentication for quick log API."""
        client = app.test_client()

        # Make request without authentication
        response = client.post(
            '/journal/api/quick-log',
            json={'plant_id': 'plant-123', 'action_type': 'water'},
            headers={'Content-Type': 'application/json'},
            follow_redirects=False
        )

        # Should redirect to login or return 401/403
        assert response.status_code in [302, 308, 401, 403]
