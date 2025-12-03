"""
Unit and integration tests for Authentication Token Lifecycle.

Tests token expiration, refresh, and session management:
- Token expiration handling
- Session verification and refresh
- Session invalidation
"""

import pytest
from unittest.mock import patch, MagicMock


class TestTokenLifecycle:
    """Test authentication token lifecycle and session management."""

    @patch('app.services.supabase_client._supabase_client')
    def test_verify_session_with_valid_token(self, mock_supabase):
        """Should verify session with valid access token."""
        from app.services.supabase_client import verify_session

        # Mock successful set_session
        mock_session_response = MagicMock()
        mock_user = MagicMock()
        mock_user.model_dump.return_value = {
            'id': 'user-123',
            'email': 'test@example.com'
        }
        mock_session_response.user = mock_user
        mock_supabase.auth.set_session.return_value = mock_session_response

        # Verify session
        user = verify_session('valid-access-token')

        # Assertions
        assert user is not None
        assert user['id'] == 'user-123'
        assert user['email'] == 'test@example.com'

    @patch('app.services.supabase_client._supabase_client')
    def test_verify_session_with_expired_token(self, mock_supabase):
        """Should return None for expired/invalid token."""
        from app.services.supabase_client import verify_session

        # Mock authentication failure (expired token)
        mock_supabase.auth.set_session.side_effect = Exception("Token expired")

        # Verify session
        user = verify_session('expired-token')

        # Assertions
        assert user is None

    @patch('app.services.supabase_client._supabase_client')
    def test_verify_session_with_refresh_token(self, mock_supabase):
        """Should use refresh token when provided."""
        from app.services.supabase_client import verify_session

        # Mock successful set_session with refresh token
        mock_session_response = MagicMock()
        mock_user = MagicMock()
        mock_user.model_dump.return_value = {
            'id': 'user-123',
            'email': 'test@example.com'
        }
        mock_session_response.user = mock_user
        mock_supabase.auth.set_session.return_value = mock_session_response

        # Verify session with refresh token
        user = verify_session('access-token', 'refresh-token')

        # Assertions
        assert user is not None
        assert user['id'] == 'user-123'

        # Verify set_session was called with both tokens
        mock_supabase.auth.set_session.assert_called_once_with(
            access_token='access-token',
            refresh_token='refresh-token'
        )


class TestSessionManagement:
    """Test Flask session management for authentication."""

    @patch('app.utils.auth.supabase_client.verify_session')
    def test_get_current_user_with_valid_session(self, mock_verify, app):
        """Should return user from valid session."""
        from app.utils.auth import get_current_user

        # Mock successful verification
        mock_verify.return_value = {
            'id': 'user-123',
            'email': 'test@example.com'
        }

        with app.test_request_context():
            # Set up session
            from flask import session
            session['access_token'] = 'valid-token'
            session['user'] = {'id': 'user-123', 'email': 'test@example.com'}

            # Get current user
            user = get_current_user()

            # Assertions
            assert user is not None
            assert user['id'] == 'user-123'

    @patch('app.utils.auth.supabase_client.verify_session')
    def test_get_current_user_clears_expired_session(self, mock_verify, app):
        """Should clear session when token is expired."""
        from app.utils.auth import get_current_user

        # Mock token expiration
        mock_verify.return_value = None

        with app.test_request_context():
            # Set up session with expired token
            from flask import session
            session['access_token'] = 'expired-token'
            session['user'] = {'id': 'user-123', 'email': 'test@example.com'}

            # Get current user
            user = get_current_user()

            # Assertions
            assert user is None
            # Session should be cleared
            assert 'access_token' not in session
            assert 'user' not in session

    def test_is_authenticated_with_no_session(self, app):
        """Should return False when no session exists."""
        from app.utils.auth import is_authenticated

        with app.test_request_context():
            # No session set
            authenticated = is_authenticated()

            # Assertions
            assert authenticated is False
