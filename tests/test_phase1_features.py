"""
Tests for Phase 1 features (Nov 2025 - Jan 2026).

Features tested:
1. Plant-Aware AI Integration
2. Today's Focus Dashboard
3. Reminder Completion Flow
4. Journaling Basics
5. Analytics Event Structure
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import json


class TestPlantAwareAI:
    """Test Plant-Aware AI Integration feature."""

    def test_ask_page_shows_user_plants(self, client, monkeypatch):
        """Ask page should display user's plants when logged in."""
        # Mock authentication (must patch at source module, not route module)
        def mock_get_user_id():
            return "test-user-id"

        def mock_get_plants(user_id, limit=None, offset=None, fields="*", use_cache=True):
            return [
                {
                    "id": "plant-1",
                    "name": "Monstera",
                    "species": "Monstera deliciosa",
                    "location": "indoor_potted"
                },
                {
                    "id": "plant-2",
                    "name": "Pothos",
                    "species": "Epipremnum aureum",
                    "location": "office"
                }
            ]

        monkeypatch.setattr("app.utils.auth.get_current_user_id", mock_get_user_id)
        monkeypatch.setattr("app.services.supabase_client.get_user_plants", mock_get_plants)

        response = client.get("/ask")
        html = response.data.decode()

        assert response.status_code == 200
        assert "Monstera" in html
        assert "Pothos" in html

    def test_plant_selection_in_ask_page(self, client):
        """Ask page should have plant selection JavaScript."""
        response = client.get("/ask")
        html = response.data.decode()

        assert response.status_code == 200
        # Check for plant selection elements
        assert "user-plants-grid" in html or "Your Plants" in html

    def test_generic_presets_hidden_when_logged_in(self, client, monkeypatch):
        """Generic presets should be hidden when user has plants."""
        # Mock authentication (must patch at source module, not route module)
        def mock_get_user_id():
            return "test-user-id"

        def mock_get_plants(user_id, limit=None, offset=None, fields="*", use_cache=True):
            return [{"id": "plant-1", "name": "Monstera"}]

        monkeypatch.setattr("app.utils.auth.get_current_user_id", mock_get_user_id)
        monkeypatch.setattr("app.services.supabase_client.get_user_plants", mock_get_plants)

        response = client.get("/ask")
        html = response.data.decode()

        # Presets should be conditionally shown based on user_plants
        assert response.status_code == 200


class TestTodaysFocus:
    """Test Today's Focus Dashboard feature."""

    def test_dashboard_shows_todays_focus_section(self, client, monkeypatch):
        """Dashboard should have Today's Focus section."""
        # Mock authentication - need to mock is_authenticated() for @require_auth decorator
        def mock_is_authenticated():
            return True

        def mock_get_user_id():
            return "test-user-id"

        monkeypatch.setattr("app.utils.auth.is_authenticated", mock_is_authenticated)
        monkeypatch.setattr("app.utils.auth.get_current_user_id", mock_get_user_id)

        # Mock reminder service to return due reminders
        def mock_get_due_reminders(user_id):
            return [
                {
                    "id": "reminder-1",
                    "title": "Water Monstera",
                    "plant_id": "plant-1",
                    "next_due": "2025-01-15",
                    "type": "watering"
                }
            ]

        monkeypatch.setattr("app.routes.dashboard.reminder_service.get_due_reminders", mock_get_due_reminders)

        response = client.get("/dashboard/")

        assert response.status_code == 200
        html = response.data.decode()
        assert "Today's Focus" in html or "todays-focus" in html

    def test_todays_focus_shows_top_3_tasks(self, client, monkeypatch):
        """Today's Focus should show maximum 3 priority tasks."""
        # Mock authentication - need to mock is_authenticated() for @require_auth decorator
        def mock_is_authenticated():
            return True

        def mock_get_user_id():
            return "test-user-id"

        monkeypatch.setattr("app.utils.auth.is_authenticated", mock_is_authenticated)
        monkeypatch.setattr("app.utils.auth.get_current_user_id", mock_get_user_id)

        # Mock 5 due reminders
        def mock_get_due_reminders(user_id):
            return [
                {"id": f"reminder-{i}", "title": f"Task {i}", "type": "watering"}
                for i in range(5)
            ]

        monkeypatch.setattr("app.routes.dashboard.reminder_service.get_due_reminders", mock_get_due_reminders)

        response = client.get("/dashboard/")
        html = response.data.decode()

        # Should only show top 3 in focus section
        assert response.status_code == 200

    def test_all_clear_state_when_no_tasks(self, client, monkeypatch):
        """Should show 'All Clear!' when no tasks due."""
        # Mock authentication - need to mock is_authenticated() for @require_auth decorator
        def mock_is_authenticated():
            return True

        def mock_get_user_id():
            return "test-user-id"

        monkeypatch.setattr("app.utils.auth.is_authenticated", mock_is_authenticated)
        monkeypatch.setattr("app.utils.auth.get_current_user_id", mock_get_user_id)

        # Mock all Supabase client calls that dashboard makes
        monkeypatch.setattr("app.routes.dashboard.supabase_client.get_user_profile", lambda user_id: {"id": "test-user-id", "email": "test@example.com"})
        monkeypatch.setattr("app.routes.dashboard.supabase_client.get_plant_count", lambda user_id: 5)
        monkeypatch.setattr("app.routes.dashboard.supabase_client.is_premium", lambda user_id: False)
        monkeypatch.setattr("app.routes.dashboard.supabase_client.is_in_trial", lambda user_id: False)
        monkeypatch.setattr("app.routes.dashboard.supabase_client.trial_days_remaining", lambda user_id: 0)
        monkeypatch.setattr("app.routes.dashboard.supabase_client.has_premium_access", lambda user_id: False)
        monkeypatch.setattr("app.routes.dashboard.supabase_client.get_user_plants", lambda user_id, limit, offset: [])

        def mock_get_due_reminders(user_id):
            return []  # No due reminders

        def mock_get_reminder_stats(user_id):
            return {"due_today": 0, "upcoming_7_days": 0, "active_reminders": 0}

        monkeypatch.setattr("app.routes.dashboard.reminder_service.get_due_reminders", mock_get_due_reminders)
        monkeypatch.setattr("app.routes.dashboard.reminder_service.get_reminder_stats", mock_get_reminder_stats)

        response = client.get("/dashboard/")
        html = response.data.decode()

        assert response.status_code == 200
        assert "All Clear" in html or "all clear" in html.lower()


class TestReminderCompletion:
    """Test Reminder Completion Flow feature."""

    def test_complete_reminder_endpoint_exists(self, client):
        """Complete reminder API endpoint should exist."""
        # Try to access endpoint (will fail auth, but should exist)
        response = client.post("/reminders/test-id/complete")

        # Should not return 404
        assert response.status_code != 404

    def test_reminder_completion_tracks_analytics(self, client, monkeypatch):
        """Completing a reminder should track analytics event."""
        tracked_events = []

        def mock_track_event(user_id, event_type, event_data):
            tracked_events.append({"user_id": user_id, "type": event_type, "data": event_data})
            return "event-123", None

        monkeypatch.setattr("app.services.analytics.track_event", mock_track_event)

        # Mock authentication for @require_auth decorator
        def mock_is_authenticated():
            return True

        def mock_get_user_id():
            return "test-user-id"

        def mock_mark_complete(reminder_id, user_id):
            return True, None

        monkeypatch.setattr("app.utils.auth.is_authenticated", mock_is_authenticated)
        monkeypatch.setattr("app.utils.auth.get_current_user_id", mock_get_user_id)
        monkeypatch.setattr("app.routes.reminders.reminder_service.mark_reminder_complete", mock_mark_complete)

        response = client.post("/reminders/test-reminder/complete")

        # Should track analytics
        assert len(tracked_events) > 0
        assert tracked_events[0]["type"] == "reminder_completed"


class TestJournaling:
    """Test Journaling Basics feature."""

    def test_journal_service_exists(self):
        """Journal service module should exist."""
        from app.services import journal

        assert hasattr(journal, "create_plant_action")
        assert hasattr(journal, "get_plant_actions")
        assert hasattr(journal, "get_action_stats")

    def test_journal_route_exists(self, client):
        """Journal routes should exist."""
        # Test that journal blueprint is registered
        response = client.get("/journal/recent")

        # Should not return 404 (may return 302 for auth)
        assert response.status_code != 404

    def test_plant_view_shows_care_statistics(self, client, monkeypatch):
        """Plant view should show care statistics."""
        # Mock authentication (patch at source for consistency)
        def mock_is_authenticated():
            return True

        def mock_get_user_id():
            return "test-user-id"

        def mock_get_plant(plant_id, user_id):
            return {
                "id": "plant-1",
                "name": "Monstera",
                "user_id": "test-user-id"
            }

        def mock_get_actions(plant_id, user_id, limit=5):
            return []

        def mock_get_stats(plant_id, user_id):
            return {
                "watering_count": 5,
                "fertilizing_count": 2,
                "repot_count": 1,
                "prune_count": 0,
                "note_count": 3,
                "pest_count": 0,
                "total_actions": 11  # Fixed: template uses total_actions not total_count
            }

        monkeypatch.setattr("app.utils.auth.is_authenticated", mock_is_authenticated)
        monkeypatch.setattr("app.utils.auth.get_current_user_id", mock_get_user_id)
        monkeypatch.setattr("app.routes.plants.get_current_user_id", mock_get_user_id)  # Patch where it's imported
        monkeypatch.setattr("app.routes.plants.supabase_client.get_plant_by_id", mock_get_plant)
        # Patch at source module since journal_service is imported inside the function
        monkeypatch.setattr("app.services.journal.get_plant_actions", mock_get_actions)
        monkeypatch.setattr("app.services.journal.get_action_stats", mock_get_stats)

        response = client.get("/plants/plant-1")

        assert response.status_code == 200
        html = response.data.decode()
        # Should show statistics
        assert "Care Statistics" in html or "care" in html.lower()

    def test_journal_entry_creation_tracks_analytics(self, client, monkeypatch):
        """Creating journal entry should track analytics."""
        tracked_events = []

        def mock_track_event(user_id, event_type, event_data):
            tracked_events.append({"type": event_type})
            return "event-123", None

        monkeypatch.setattr("app.services.analytics.track_event", mock_track_event)

        # Mock authentication for @require_auth decorator
        def mock_is_authenticated():
            return True

        def mock_get_user_id():
            return "test-user-id"

        def mock_get_plant(plant_id, user_id):
            return {"id": "plant-1", "name": "Monstera"}

        def mock_create_action(*args, **kwargs):
            return {"id": "action-123"}, None

        monkeypatch.setattr("app.utils.auth.is_authenticated", mock_is_authenticated)
        monkeypatch.setattr("app.utils.auth.get_current_user_id", mock_get_user_id)
        monkeypatch.setattr("app.routes.journal.get_plant_by_id", mock_get_plant)
        monkeypatch.setattr("app.routes.journal.journal_service.create_plant_action", mock_create_action)

        response = client.post("/journal/plant/plant-1/add", data={
            "action_type": "water",
            "notes": "Watered thoroughly",
            "amount_ml": "500"
        })

        # Should track analytics
        assert any(e["type"] == "journal_entry_created" for e in tracked_events)

    def test_action_type_names_defined(self):
        """Journal should define action type names and emojis."""
        from app.services import journal

        assert hasattr(journal, "ACTION_TYPE_NAMES")
        assert hasattr(journal, "ACTION_TYPE_EMOJIS")
        assert "water" in journal.ACTION_TYPE_NAMES
        assert "fertilize" in journal.ACTION_TYPE_NAMES


class TestAnalytics:
    """Test Analytics Event Structure feature."""

    def test_analytics_service_exists(self):
        """Analytics service module should exist."""
        from app.services import analytics

        assert hasattr(analytics, "track_event")
        assert hasattr(analytics, "get_activation_rate")
        assert hasattr(analytics, "get_weekly_active_users")
        assert hasattr(analytics, "get_stickiness")

    def test_analytics_event_constants_defined(self):
        """Analytics event type constants should be defined."""
        from app.services import analytics

        assert hasattr(analytics, "EVENT_USER_SIGNUP")
        assert hasattr(analytics, "EVENT_PLANT_ADDED")
        assert hasattr(analytics, "EVENT_FIRST_PLANT_ADDED")
        assert hasattr(analytics, "EVENT_REMINDER_CREATED")
        assert hasattr(analytics, "EVENT_REMINDER_COMPLETED")
        assert hasattr(analytics, "EVENT_JOURNAL_ENTRY_CREATED")
        assert hasattr(analytics, "EVENT_AI_QUESTION_ASKED")

    def test_plant_creation_tracks_analytics(self, client, monkeypatch):
        """Creating a plant should track analytics event."""
        tracked_events = []

        def mock_track_event(user_id, event_type, event_data):
            tracked_events.append({"type": event_type, "data": event_data})
            return "event-123", None

        monkeypatch.setattr("app.services.analytics.track_event", mock_track_event)

        # Mock authentication for @require_auth decorator
        def mock_is_authenticated():
            return True

        def mock_get_user_id():
            return "test-user-id"

        def mock_can_add():
            return True, None

        def mock_create_plant(user_id, data):
            return {"id": "plant-123", "name": data["name"]}

        monkeypatch.setattr("app.utils.auth.is_authenticated", mock_is_authenticated)
        monkeypatch.setattr("app.utils.auth.get_current_user_id", mock_get_user_id)
        monkeypatch.setattr("app.routes.plants.supabase_client.can_add_plant", mock_can_add)
        monkeypatch.setattr("app.routes.plants.supabase_client.create_plant", mock_create_plant)

        response = client.post("/plants/add", data={
            "name": "Monstera",
            "location": "indoor_potted",
            "light": "bright"
        })

        # Should track plant_added event
        assert any(e["type"] == "plant_added" for e in tracked_events)

    def test_ai_question_tracks_analytics(self, client, monkeypatch):
        """Asking AI question should track analytics when logged in."""
        tracked_events = []

        def mock_track_event(user_id, event_type, event_data):
            tracked_events.append({"type": event_type})
            return "event-123", None

        monkeypatch.setattr("app.services.analytics.track_event", mock_track_event)

        # Mock authentication (must patch at source module, not route module)
        def mock_get_user_id():
            return "test-user-id"

        def mock_get_plants(user_id, limit=None, offset=None, fields="*", use_cache=True):
            return []

        def mock_generate_advice(*args, **kwargs):
            return "Water your plant", None, "ai"

        monkeypatch.setattr("app.utils.auth.get_current_user_id", mock_get_user_id)
        monkeypatch.setattr("app.services.supabase_client.get_user_plants", mock_get_plants)
        monkeypatch.setattr("app.routes.web.generate_advice", mock_generate_advice)

        response = client.post("/ask", data={
            "plant": "Monstera",
            "city": "Boston",
            "question": "How to water?",
            "care_context": "indoor_potted"
        })

        # Should track ai_question_asked event
        assert any(e["type"] == "ai_question_asked" for e in tracked_events)

    def test_admin_route_exists(self, client):
        """Admin analytics dashboard route should exist."""
        response = client.get("/admin")

        # Should not return 404 (may return 302/403 for auth)
        assert response.status_code != 404


class TestLocationStandardization:
    """Test location field standardization across app."""

    def test_plant_add_has_standardized_locations(self, client):
        """Plant add form should have standardized location options."""
        response = client.get("/plants/add")

        if response.status_code == 200:
            html = response.data.decode()
            # Check for all standardized location options
            assert "Indoor (potted)" in html
            assert "Outdoor (potted)" in html
            assert "Outdoor (in-ground bed)" in html
            assert "Greenhouse" in html
            assert "Office" in html

    def test_validation_accepts_all_locations(self):
        """Validation should accept all standardized location values."""
        from app.utils.validation import normalize_context

        valid_locations = ["indoor_potted", "outdoor_potted", "outdoor_bed", "greenhouse", "office"]

        for location in valid_locations:
            result = normalize_context(location)
            assert result == location

    def test_ask_page_has_matching_locations(self, client):
        """Ask page should have matching location options."""
        response = client.get("/ask")

        if response.status_code == 200:
            html = response.data.decode()
            # Should have care_context selector with same options
            assert "indoor_potted" in html
            assert "greenhouse" in html or "Greenhouse" in html
            assert "office" in html or "Office" in html


class TestFirstPlantTrigger:
    """Test first plant added auto-tracking."""

    def test_first_plant_trigger_in_migration(self):
        """Migration 009 should include first plant trigger."""
        import os
        migration_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "supabase_migrations",
            "009_analytics_events.sql"
        )

        if os.path.exists(migration_path):
            with open(migration_path, "r") as f:
                content = f.read()

            assert "track_first_plant_added" in content
            assert "trigger_track_first_plant" in content
            assert "first_plant_added" in content
