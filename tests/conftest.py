# tests/conftest.py
"""
Test configuration and shared fixtures.

Provides Flask app, test client, and database fixtures for pytest.
"""

import os
import sys
import pytest
from unittest.mock import Mock, MagicMock

# Add the project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def app():
    """Create and configure a Flask app instance for testing."""
    # Set test environment variables before importing app
    os.environ["FLASK_ENV"] = "testing"
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
    os.environ["SUPABASE_URL"] = "https://test.supabase.co"
    os.environ["SUPABASE_KEY"] = "test-key"
    os.environ["APP_CONFIG"] = "app.config.TestConfig"

    from app import create_app

    app = create_app()
    app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,  # Disable CSRF for tests
        "RATELIMIT_ENABLED": False,  # Disable rate limiting for tests
    })

    yield app


@pytest.fixture
def client(app):
    """Create a test client for the Flask app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner for the Flask app."""
    return app.test_cli_runner()


@pytest.fixture
def auth_headers():
    """Return headers for an authenticated request."""
    return {
        "Authorization": "Bearer test-token",
        "X-CSRFToken": "test-csrf-token"
    }


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing without real database."""
    mock_client = MagicMock()

    # Mock common Supabase operations
    mock_client.auth.get_user.return_value = Mock(
        user=Mock(id="test-user-id", email="test@example.com")
    )
    mock_client.table.return_value.select.return_value.execute.return_value = Mock(
        data=[]
    )

    return mock_client


@pytest.fixture
def mock_user_session(app, monkeypatch):
    """Mock a logged-in user session."""
    with app.test_request_context():
        from flask import session
        session["user"] = {
            "id": "test-user-id",
            "email": "test@example.com",
            "access_token": "test-token"
        }
        yield session


@pytest.fixture
def sample_plant():
    """Sample plant data for testing."""
    return {
        "id": "plant-123",
        "user_id": "test-user-id",
        "name": "Monstera Deliciosa",
        "species": "Monstera deliciosa",
        "nickname": "Monty",
        "location": "indoor_potted",
        "light": "bright",
        "notes": "Water weekly",
        "photo_url": None,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_reminder():
    """Sample reminder data for testing."""
    return {
        "id": "reminder-123",
        "user_id": "test-user-id",
        "plant_id": "plant-123",
        "title": "Water Monstera",
        "type": "watering",
        "frequency": "weekly",
        "next_due": "2025-01-15",
        "is_active": True,
        "is_recurring": True,
        "notes": "Water thoroughly",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_journal_entry():
    """Sample journal entry data for testing."""
    return {
        "id": "action-123",
        "user_id": "test-user-id",
        "plant_id": "plant-123",
        "action_type": "water",
        "action_at": "2025-01-01T10:00:00Z",
        "amount_ml": 500,
        "notes": "Watered thoroughly",
        "photo_url": None,
        "created_at": "2025-01-01T10:00:00Z"
    }


@pytest.fixture
def with_openai_key(monkeypatch):
    """Set OpenAI API key environment variable."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")


@pytest.fixture
def with_gemini_key(monkeypatch):
    """Set Gemini API key environment variable."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")


@pytest.fixture
def without_ai_keys(monkeypatch):
    """Remove AI API keys to test fallback behavior."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
