"""
Unit and integration tests for Plant CRUD operations.

Tests the plant update (edit) and delete routes, including:
- Plant information updates
- Photo management (upload, delete)
- Cascading deletes (reminders, journal entries)
- Authorization and validation
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from io import BytesIO


class TestPlantUpdate:
    """Test plant update (edit) operations."""

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.routes.plants.supabase_client.update_plant')
    def test_update_plant_name(self, mock_update, mock_get, mock_auth, app, sample_plant):
        """Should update plant name successfully."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock getting existing plant
        mock_get.return_value = sample_plant

        # Mock successful update
        updated_plant = {**sample_plant, 'name': 'New Name'}
        mock_update.return_value = updated_plant

        # Make request
        response = client.post(
            '/plants/plant-123/edit',
            data={
                'name': 'New Name',
                'species': sample_plant['species'],
                'nickname': sample_plant['nickname'],
                'location': sample_plant['location'],
                'light': sample_plant['light'],
                'notes': sample_plant['notes']
            },
            follow_redirects=False
        )

        # Assertions
        assert response.status_code == 302  # Redirect to view page
        assert '/plants/plant-123' in response.location

        # Verify service was called with updated data
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][0] == 'plant-123'  # plant_id
        assert call_args[0][1] == 'test-user-id'  # user_id
        assert call_args[0][2]['name'] == 'New Name'

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.routes.plants.supabase_client.update_plant')
    def test_update_plant_location_and_light(self, mock_update, mock_get, mock_auth, app, sample_plant):
        """Should update plant location and light settings."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock getting existing plant
        mock_get.return_value = sample_plant

        # Mock successful update
        updated_plant = {
            **sample_plant,
            'location': 'outdoor_ground',
            'light': 'full_sun'
        }
        mock_update.return_value = updated_plant

        # Make request
        response = client.post(
            '/plants/plant-123/edit',
            data={
                'name': sample_plant['name'],
                'species': sample_plant['species'],
                'nickname': sample_plant['nickname'],
                'location': 'outdoor_ground',
                'light': 'full_sun',
                'notes': sample_plant['notes']
            },
            follow_redirects=False
        )

        # Assertions
        assert response.status_code == 302

        # Verify updated fields
        call_args = mock_update.call_args
        assert call_args[0][2]['location'] == 'outdoor_ground'
        assert call_args[0][2]['light'] == 'full_sun'

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.routes.plants.supabase_client.update_plant')
    @patch('app.routes.plants.supabase_client.upload_plant_photo_versions')
    @patch('app.routes.plants.validate_upload_file')
    @patch('app.services.supabase_client.delete_plant_photo')
    def test_update_plant_with_new_photo(
        self, mock_delete_photo, mock_validate, mock_upload, mock_update, mock_get, mock_auth, app, sample_plant
    ):
        """Should upload new photo and delete old one when updating plant."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock existing plant with old photo (use realistic storage URLs)
        plant_with_photo = {
            **sample_plant,
            'photo_url': 'https://storage.example.com/plant-photos/user123/old-photo.jpg',
            'photo_url_thumb': 'https://storage.example.com/plant-photos/user123/old-photo-thumb.jpg'
        }
        mock_get.return_value = plant_with_photo

        # Mock file validation to return success
        fake_file_bytes = b'fake image data'
        mock_validate.return_value = (True, None, fake_file_bytes)

        # Mock successful photo upload
        mock_upload.return_value = (
            {
                'display': 'https://storage.example.com/plant-photos/user123/new-photo.jpg',
                'thumbnail': 'https://storage.example.com/plant-photos/user123/new-photo-thumb.jpg'
            },
            None  # No error
        )

        # Mock successful update
        mock_update.return_value = {**plant_with_photo, 'photo_url': 'https://storage.example.com/plant-photos/user123/new-photo.jpg'}

        # Create fake file upload
        file_data = BytesIO(b'fake image data')
        file_data.name = 'test.jpg'

        # Make request with file
        response = client.post(
            '/plants/plant-123/edit',
            data={
                'name': sample_plant['name'],
                'species': sample_plant['species'],
                'nickname': sample_plant['nickname'],
                'location': sample_plant['location'],
                'light': sample_plant['light'],
                'notes': sample_plant['notes'],
                'photo': (file_data, 'test.jpg')
            },
            content_type='multipart/form-data',
            follow_redirects=False
        )

        # Assertions
        assert response.status_code == 302

        # Verify file was validated
        mock_validate.assert_called_once()

        # Verify old photos were deleted (2 calls: display + thumbnail)
        assert mock_delete_photo.call_count >= 2

        # Verify update was called with new photo URLs
        call_args = mock_update.call_args
        assert 'new-photo.jpg' in call_args[0][2]['photo_url']
        assert 'new-photo-thumb.jpg' in call_args[0][2]['photo_url_thumb']

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.routes.plants.supabase_client.update_plant')
    @patch('app.services.supabase_client.delete_plant_photo')
    def test_update_plant_delete_photo(
        self, mock_delete_photo, mock_update, mock_get, mock_auth, app, sample_plant
    ):
        """Should delete photo when delete_photo checkbox is checked."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock existing plant with photo (use realistic storage URLs)
        plant_with_photo = {
            **sample_plant,
            'photo_url': 'https://storage.example.com/plant-photos/user123/old-photo.jpg',
            'photo_url_thumb': 'https://storage.example.com/plant-photos/user123/old-photo-thumb.jpg'
        }
        mock_get.return_value = plant_with_photo

        # Mock successful update
        mock_update.return_value = {**plant_with_photo, 'photo_url': None}

        # Make request with delete_photo flag
        response = client.post(
            '/plants/plant-123/edit',
            data={
                'name': sample_plant['name'],
                'species': sample_plant['species'],
                'nickname': sample_plant['nickname'],
                'location': sample_plant['location'],
                'light': sample_plant['light'],
                'notes': sample_plant['notes'],
                'delete_photo': 'true'
            },
            follow_redirects=False
        )

        # Assertions
        assert response.status_code == 302

        # Verify photos were deleted (2 calls: display + thumbnail)
        assert mock_delete_photo.call_count >= 2

        # Verify update was called with null photo URLs
        call_args = mock_update.call_args
        assert call_args[0][2]['photo_url'] is None
        assert call_args[0][2]['photo_url_thumb'] is None

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    def test_update_plant_validates_name_required(self, mock_get, mock_auth, app, sample_plant):
        """Should reject update when plant name is missing."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock getting existing plant
        mock_get.return_value = sample_plant

        # Make request without name
        response = client.post(
            '/plants/plant-123/edit',
            data={
                'name': '',  # Empty name
                'species': sample_plant['species'],
                'nickname': sample_plant['nickname'],
                'location': sample_plant['location'],
                'light': sample_plant['light'],
                'notes': sample_plant['notes']
            },
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200
        assert b'Plant name is required' in response.data

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    def test_update_plant_validates_ownership(self, mock_get, mock_auth, app):
        """Should reject update when plant not found or doesn't belong to user."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock plant not found
        mock_get.return_value = None

        # Make request
        response = client.post(
            '/plants/plant-123/edit',
            data={'name': 'Test'},
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200
        assert b'Plant not found' in response.data

    def test_update_plant_requires_auth(self, app):
        """Should require authentication to update plant."""
        client = app.test_client()

        # Make request without authentication
        response = client.post(
            '/plants/plant-123/edit',
            data={'name': 'Test'},
            follow_redirects=False
        )

        # Should redirect to login
        assert response.status_code in [302, 308, 401, 403]

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.routes.plants.supabase_client.update_plant')
    def test_update_plant_handles_update_failure(self, mock_update, mock_get, mock_auth, app, sample_plant):
        """Should handle gracefully when update operation fails."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock getting existing plant
        mock_get.return_value = sample_plant

        # Mock update failure
        mock_update.return_value = None

        # Make request
        response = client.post(
            '/plants/plant-123/edit',
            data={
                'name': 'New Name',
                'species': sample_plant['species'],
                'nickname': sample_plant['nickname'],
                'location': sample_plant['location'],
                'light': sample_plant['light'],
                'notes': sample_plant['notes']
            },
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200
        assert b'Failed to update plant' in response.data


class TestPlantDelete:
    """Test plant delete operations."""

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.routes.plants.supabase_client.delete_plant')
    @patch('app.utils.photo_handler.delete_all_photo_versions')
    def test_delete_plant_success(self, mock_delete_photos, mock_delete, mock_get, mock_auth, app, sample_plant):
        """Should delete plant successfully."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock getting existing plant
        mock_get.return_value = sample_plant

        # Mock successful deletion
        mock_delete.return_value = True

        # Make request
        response = client.post(
            '/plants/plant-123/delete',
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200
        assert b'removed from your collection' in response.data

        # Verify deletion was called
        mock_delete.assert_called_once_with('plant-123', 'test-user-id')

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.routes.plants.supabase_client.delete_plant')
    @patch('app.services.supabase_client.delete_plant_photo')
    def test_delete_plant_with_photos(self, mock_delete_photo, mock_delete, mock_get, mock_auth, app, sample_plant):
        """Should delete plant photos when deleting plant."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock existing plant with photos (use realistic storage URLs)
        plant_with_photo = {
            **sample_plant,
            'photo_url': 'https://storage.example.com/plant-photos/user123/photo.jpg',
            'photo_url_thumb': 'https://storage.example.com/plant-photos/user123/photo-thumb.jpg'
        }
        mock_get.return_value = plant_with_photo

        # Mock successful deletion
        mock_delete.return_value = True

        # Make request
        response = client.post(
            '/plants/plant-123/delete',
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200

        # Verify photos were deleted before plant deletion (2 calls: display + thumbnail)
        assert mock_delete_photo.call_count >= 2

        # Verify plant deletion was called
        mock_delete.assert_called_once()

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    def test_delete_plant_validates_ownership(self, mock_get, mock_auth, app):
        """Should reject deletion when plant not found or doesn't belong to user."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock plant not found
        mock_get.return_value = None

        # Make request
        response = client.post(
            '/plants/plant-123/delete',
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200
        assert b'Plant not found' in response.data

    def test_delete_plant_requires_auth(self, app):
        """Should require authentication to delete plant."""
        client = app.test_client()

        # Make request without authentication
        response = client.post(
            '/plants/plant-123/delete',
            follow_redirects=False
        )

        # Should redirect to login
        assert response.status_code in [302, 308, 401, 403]

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.routes.plants.supabase_client.delete_plant')
    @patch('app.utils.photo_handler.delete_all_photo_versions')
    def test_delete_plant_handles_deletion_failure(
        self, mock_delete_photos, mock_delete, mock_get, mock_auth, app, sample_plant
    ):
        """Should handle gracefully when deletion operation fails."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock getting existing plant
        mock_get.return_value = sample_plant

        # Mock deletion failure
        mock_delete.return_value = False

        # Make request
        response = client.post(
            '/plants/plant-123/delete',
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200
        assert b'Failed to delete plant' in response.data

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.routes.plants.supabase_client.delete_plant')
    @patch('app.utils.photo_handler.delete_all_photo_versions')
    def test_delete_plant_includes_plant_name_in_message(
        self, mock_delete_photos, mock_delete, mock_get, mock_auth, app, sample_plant
    ):
        """Should include plant name in success message."""
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock getting existing plant
        mock_get.return_value = sample_plant

        # Mock successful deletion
        mock_delete.return_value = True

        # Make request
        response = client.post(
            '/plants/plant-123/delete',
            follow_redirects=True
        )

        # Assertions
        assert response.status_code == 200
        # Should include plant name in flash message
        assert sample_plant['name'].encode() in response.data or b'Monstera Deliciosa' in response.data


class TestPlantCascadingDeletes:
    """
    Test that plant deletion properly cascades to related data.

    Note: Cascade behavior is handled at the database level via foreign key constraints.
    These tests verify that the application layer doesn't prevent cascades.
    """

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.routes.plants.supabase_client.delete_plant')
    @patch('app.utils.photo_handler.delete_all_photo_versions')
    def test_delete_plant_allows_cascade_to_reminders(
        self, mock_delete_photos, mock_delete, mock_get, mock_auth, app, sample_plant
    ):
        """
        Should allow deletion even if plant has reminders.

        Database CASCADE foreign key will handle reminder deletion.
        """
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock getting existing plant (assume it has reminders via FK)
        mock_get.return_value = sample_plant

        # Mock successful deletion (database handles cascade)
        mock_delete.return_value = True

        # Make request
        response = client.post(
            '/plants/plant-123/delete',
            follow_redirects=True
        )

        # Assertions - should succeed despite having related reminders
        assert response.status_code == 200
        assert b'removed from your collection' in response.data
        mock_delete.assert_called_once_with('plant-123', 'test-user-id')

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.routes.plants.supabase_client.delete_plant')
    @patch('app.utils.photo_handler.delete_all_photo_versions')
    def test_delete_plant_allows_cascade_to_journal(
        self, mock_delete_photos, mock_delete, mock_get, mock_auth, app, sample_plant
    ):
        """
        Should allow deletion even if plant has journal entries.

        Database CASCADE foreign key will handle journal entry deletion.
        """
        client = app.test_client()

        # Mock authentication
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}

        # Mock getting existing plant (assume it has journal entries via FK)
        mock_get.return_value = sample_plant

        # Mock successful deletion (database handles cascade)
        mock_delete.return_value = True

        # Make request
        response = client.post(
            '/plants/plant-123/delete',
            follow_redirects=True
        )

        # Assertions - should succeed despite having journal entries
        assert response.status_code == 200
        assert b'removed from your collection' in response.data
        mock_delete.assert_called_once_with('plant-123', 'test-user-id')


class TestPlantViewReminders:
    """Test Care Reminders section on plant view page."""

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.services.journal.get_plant_actions')
    @patch('app.services.journal.get_action_stats')
    @patch('app.services.reminders.get_user_reminders')
    def test_plant_view_shows_reminders_section(
        self, mock_reminders, mock_stats, mock_actions, mock_get_plant, mock_auth, app, sample_plant
    ):
        """Plant view page should include care reminders section."""
        client = app.test_client()
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}
        mock_get_plant.return_value = sample_plant
        mock_actions.return_value = []
        mock_stats.return_value = {'total_actions': 0}
        mock_reminders.return_value = []

        response = client.get('/plants/plant-123')

        assert response.status_code == 200
        assert b'Care Reminders' in response.data
        assert b'Add Reminder' in response.data

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.services.journal.get_plant_actions')
    @patch('app.services.journal.get_action_stats')
    @patch('app.services.reminders.get_user_reminders')
    def test_plant_view_shows_plant_reminders(
        self, mock_reminders, mock_stats, mock_actions, mock_get_plant, mock_auth, app, sample_plant, sample_reminder
    ):
        """Plant view should display reminders for that plant."""
        client = app.test_client()
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}
        mock_get_plant.return_value = sample_plant
        mock_actions.return_value = []
        mock_stats.return_value = {'total_actions': 0}
        mock_reminders.return_value = [sample_reminder]

        response = client.get('/plants/plant-123')

        assert response.status_code == 200
        assert sample_reminder['title'].encode() in response.data

    @patch('app.utils.auth.get_current_user')
    @patch('app.routes.plants.supabase_client.get_plant_by_id')
    @patch('app.services.journal.get_plant_actions')
    @patch('app.services.journal.get_action_stats')
    @patch('app.services.reminders.get_user_reminders')
    def test_plant_view_empty_reminders_state(
        self, mock_reminders, mock_stats, mock_actions, mock_get_plant, mock_auth, app, sample_plant
    ):
        """Plant view should show empty state when no reminders exist."""
        client = app.test_client()
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}
        mock_get_plant.return_value = sample_plant
        mock_actions.return_value = []
        mock_stats.return_value = {'total_actions': 0}
        mock_reminders.return_value = []

        response = client.get('/plants/plant-123')

        assert response.status_code == 200
        assert b'No reminders yet' in response.data
        assert b'Create First Reminder' in response.data


class TestReminderCreatePreselection:
    """Test reminder create page with plant pre-selection."""

    @patch('app.utils.auth.get_current_user')
    @patch('app.services.supabase_client.get_user_plants')
    def test_create_reminder_preselects_plant(self, mock_plants, mock_auth, app, sample_plant):
        """Creating reminder with plant_id query param should pre-select plant."""
        client = app.test_client()
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}
        mock_plants.return_value = [sample_plant]

        response = client.get(f'/reminders/create?plant_id={sample_plant["id"]}')

        assert response.status_code == 200
        assert b'selected' in response.data
        # Check plant name appears in "Creating reminder for..." text
        assert b'Creating reminder for' in response.data
        assert sample_plant['name'].encode() in response.data

    @patch('app.utils.auth.get_current_user')
    @patch('app.services.supabase_client.get_user_plants')
    def test_create_reminder_invalid_plant_id_ignored(self, mock_plants, mock_auth, app, sample_plant):
        """Invalid plant_id should be ignored, not cause error."""
        client = app.test_client()
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}
        mock_plants.return_value = [sample_plant]

        response = client.get('/reminders/create?plant_id=invalid-uuid')

        assert response.status_code == 200
        assert b'Select a plant...' in response.data
        # Should NOT show "Creating reminder for"
        assert b'Creating reminder for' not in response.data

    @patch('app.utils.auth.get_current_user')
    @patch('app.services.supabase_client.get_user_plants')
    def test_create_reminder_plant_dropdown_disabled_when_preselected(
        self, mock_plants, mock_auth, app, sample_plant
    ):
        """Plant dropdown should be disabled when pre-selected."""
        client = app.test_client()
        mock_auth.return_value = {'id': 'test-user-id', 'email': 'test@example.com'}
        mock_plants.return_value = [sample_plant]

        response = client.get(f'/reminders/create?plant_id={sample_plant["id"]}')

        assert response.status_code == 200
        assert b'disabled' in response.data
        # Hidden input should be present for form submission
        assert f'type="hidden" name="plant_id" value="{sample_plant["id"]}"'.encode() in response.data
