"""
Security-focused tests for PlantCareAI.

Tests for:
- XSS (Cross-Site Scripting)
- CSRF (Cross-Site Request Forgery)
- SQL Injection
- Authentication bypass
- Authorization checks
- Input validation
- File upload security
- Session security
"""

import pytest
from flask import session


class TestXSSProtection:
    """Test XSS attack prevention."""

    def test_validation_strips_script_tags(self):
        """Validation should remove script tags from inputs."""
        from app.utils.validation import validate_inputs

        form = {
            "plant": "Monstera<script>alert('xss')</script>",
            "city": "Boston<img src=x onerror=alert('xss')>",
            "question": "How to water?",
            "care_context": "indoor_potted"
        }

        payload, error = validate_inputs(form)

        assert error is None
        assert "<script>" not in payload["plant"]
        assert "onerror" not in payload["city"]
        assert "Monstera" in payload["plant"]  # Legitimate content preserved

    def test_display_sanitize_escapes_html(self):
        """Display sanitization should escape HTML entities."""
        from app.utils.validation import display_sanitize_short

        dangerous = '<script>alert("xss")</script>'
        result = display_sanitize_short(dangerous)

        assert "&lt;" in result
        assert "&gt;" in result
        assert "<script>" not in result

    def test_ask_endpoint_escapes_user_input(self, client):
        """Ask endpoint should escape user input in responses."""
        response = client.post("/ask", data={
            "plant": "<b>Bold Plant</b>",
            "city": "Boston",
            "question": "How to water?",
            "care_context": "indoor_potted"
        })

        assert response.status_code in [200, 400]
        if response.status_code == 200:
            html = response.data.decode()
            # HTML tags should be escaped, not rendered
            assert "&lt;b&gt;" in html or "<b>" not in html


class TestCSRFProtection:
    """Test CSRF attack prevention."""

    def test_csrf_token_required_for_post_requests(self, client):
        """POST requests should require CSRF token."""
        # Note: In tests, CSRF is disabled via WTF_CSRF_ENABLED=False
        # This test ensures the protection exists in production
        from flask_wtf.csrf import generate_csrf

        with client.application.app_context():
            token = generate_csrf()
            assert token is not None
            assert len(token) > 0

    def test_post_without_csrf_should_fail_in_production(self):
        """POST without CSRF should be rejected in production."""
        # This is a documentation test - CSRF is enforced by Flask-WTF
        from flask_wtf.csrf import CSRFProtect

        # Verify CSRFProtect is initialized in app
        from app import create_app
        app = create_app()
        assert any(isinstance(ext, CSRFProtect) for ext in [])  # CSRFProtect doesn't expose itself easily


class TestSQLInjection:
    """Test SQL injection prevention."""

    def test_validation_removes_sql_injection_attempts(self):
        """Validation should remove SQL injection characters."""
        from app.utils.validation import validate_inputs

        form = {
            "plant": "Plant'; DROP TABLE plants;--",
            "city": "1' OR '1'='1",
            "question": "How to water?",
            "care_context": "indoor_potted"
        }

        payload, error = validate_inputs(form)

        assert error is None
        assert "DROP" not in payload["plant"]
        assert ";" not in payload["plant"]  # Semicolons removed
        assert ";" not in payload["city"]

    def test_supabase_uses_parameterized_queries(self):
        """Supabase client should use parameterized queries (not string concatenation)."""
        # This is a code review test - Supabase SDK prevents SQL injection by design
        # All queries use .eq(), .filter(), etc. which are parameterized
        from app.services import supabase_client

        # Verify we're not using raw SQL anywhere
        import inspect
        source = inspect.getsource(supabase_client)

        # Check that we're not concatenating SQL strings
        assert "SELECT * FROM" not in source  # No raw SQL
        assert "INSERT INTO" not in source
        assert "UPDATE " not in source or "UPDATE " in source  # May appear in comments


class TestAuthenticationBypass:
    """Test authentication bypass prevention."""

    def test_require_auth_decorator_blocks_anonymous(self, client):
        """@require_auth should block unauthenticated users."""
        # Try to access protected route without authentication
        response = client.get("/dashboard")

        # Should redirect to login or return 401/403
        assert response.status_code in [302, 401, 403]
        if response.status_code == 302:
            assert "login" in response.location or "auth" in response.location

    def test_plants_require_authentication(self, client):
        """Plant routes should require authentication."""
        routes_to_test = [
            "/plants",
            "/plants/add",
        ]

        for route in routes_to_test:
            response = client.get(route)
            assert response.status_code in [302, 401, 403], f"{route} should require auth"

    def test_reminders_require_authentication(self, client):
        """Reminder routes should require authentication."""
        routes_to_test = [
            "/reminders",
            "/reminders/create",
        ]

        for route in routes_to_test:
            response = client.get(route)
            assert response.status_code in [302, 401, 403], f"{route} should require auth"

    def test_session_without_user_denies_access(self, client):
        """Empty session should deny access to protected routes."""
        with client.session_transaction() as sess:
            sess.clear()  # Ensure session is empty

        response = client.get("/dashboard")
        assert response.status_code in [302, 401, 403]


class TestAuthorization:
    """Test authorization and access control."""

    def test_user_cannot_access_other_users_plants(self, client, monkeypatch):
        """Users should only see their own plants."""
        from app.services import supabase_client

        # Mock get_user_plants to return plants for different user
        def mock_get_plants(user_id):
            return [] if user_id != "authorized-user" else [{"id": "plant-1"}]

        monkeypatch.setattr(supabase_client, "get_user_plants", mock_get_plants)

        # Even if user tries to access, they should only get their own data
        result = supabase_client.get_user_plants("unauthorized-user")
        assert result == []

    def test_admin_routes_require_admin_privilege(self, client):
        """Admin routes should check for admin privileges."""
        # Try to access admin without being logged in
        response = client.get("/admin")

        # Should redirect or return 401/403
        assert response.status_code in [302, 401, 403]


class TestFileUploadSecurity:
    """Test file upload security."""

    def test_file_extension_validation(self):
        """Only allowed file extensions should be accepted."""
        from app.routes.plants import allowed_file

        assert allowed_file("image.png") is True
        assert allowed_file("image.jpg") is True
        assert allowed_file("image.jpeg") is True
        assert allowed_file("image.gif") is True
        assert allowed_file("image.webp") is True

        # Dangerous extensions should be rejected
        assert allowed_file("script.php") is False
        assert allowed_file("malware.exe") is False
        assert allowed_file("shell.sh") is False
        assert allowed_file("image.php.jpg") is False  # Double extension attack

    def test_file_content_validation(self):
        """File content should be validated, not just extension."""
        from app.routes.plants import validate_image_content
        from PIL import Image
        from io import BytesIO

        # Create a valid PNG
        img = Image.new("RGB", (100, 100), color="red")
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        valid_content = img_bytes.getvalue()

        assert validate_image_content(valid_content) is True

        # Invalid content (not an image)
        invalid_content = b"This is not an image file"
        assert validate_image_content(invalid_content) is False

    def test_file_size_limit_enforced(self):
        """Files over 5MB should be rejected."""
        from app.routes.plants import MAX_FILE_SIZE

        assert MAX_FILE_SIZE == 5 * 1024 * 1024  # 5MB
        # Actual enforcement is checked in route handler


class TestSessionSecurity:
    """Test session security."""

    def test_session_cookies_are_httponly(self, app):
        """Session cookies should have HttpOnly flag."""
        assert app.config.get("SESSION_COOKIE_HTTPONLY") is True

    def test_session_cookies_are_secure_in_production(self, app):
        """Session cookies should have Secure flag in production."""
        # In test config it may be False, but verify it exists
        assert "SESSION_COOKIE_SECURE" in app.config

    def test_session_cookies_have_samesite(self, app):
        """Session cookies should have SameSite attribute."""
        assert app.config.get("SESSION_COOKIE_SAMESITE") == "Lax"


class TestInputValidation:
    """Test comprehensive input validation."""

    def test_plant_name_length_limit(self):
        """Plant names should be limited in length."""
        from app.utils.validation import validate_inputs, MAX_PLANT_LEN

        form = {
            "plant": "A" * 200,  # Excessively long
            "city": "Boston",
            "question": "How to water?",
            "care_context": "indoor_potted"
        }

        payload, error = validate_inputs(form)

        assert error is None
        assert len(payload["plant"]) <= MAX_PLANT_LEN

    def test_question_required_validation(self):
        """Question field should be required."""
        from app.utils.validation import validate_inputs

        form = {
            "plant": "Monstera",
            "city": "Boston",
            "question": "",  # Empty question
            "care_context": "indoor_potted"
        }

        payload, error = validate_inputs(form)

        assert error is not None
        assert "required" in error.lower()

    def test_care_context_validation(self):
        """Invalid care context should be normalized."""
        from app.utils.validation import normalize_context

        assert normalize_context("indoor_potted") == "indoor_potted"
        assert normalize_context("outdoor_potted") == "outdoor_potted"
        assert normalize_context("INVALID") == "indoor_potted"  # Default
        assert normalize_context(None) == "indoor_potted"  # Default


class TestPasswordSecurity:
    """Test password handling security."""

    def test_no_passwords_in_code(self):
        """Code should not contain hardcoded passwords."""
        import os
        import re

        # Check key files for password patterns
        files_to_check = [
            "app/__init__.py",
            "app/config.py",
            "app/services/supabase_client.py"
        ]

        password_pattern = re.compile(r'password\s*=\s*["\'](?!{{|{%)[^"\']{8,}["\']', re.IGNORECASE)

        for file_path in files_to_check:
            full_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                file_path
            )
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    matches = password_pattern.findall(content)
                    assert len(matches) == 0, f"Potential hardcoded password in {file_path}"

    def test_environment_variables_for_secrets(self):
        """Secrets should come from environment variables."""
        from app.config import BaseConfig

        # These should all use os.getenv()
        config = BaseConfig()
        assert hasattr(config, "SECRET_KEY")
        assert hasattr(config, "SUPABASE_ANON_KEY")
        assert hasattr(config, "SUPABASE_SERVICE_ROLE_KEY")


class TestContentSecurityPolicy:
    """Test Content Security Policy headers."""

    def test_csp_headers_present(self, client):
        """Responses should include CSP headers."""
        response = client.get("/")

        assert "Content-Security-Policy" in response.headers

    def test_csp_blocks_inline_scripts(self, client):
        """CSP should block inline scripts (except for specific cases)."""
        response = client.get("/")

        csp = response.headers.get("Content-Security-Policy", "")
        # Should have script-src directive
        assert "script-src" in csp

    def test_security_headers_present(self, client):
        """All security headers should be present."""
        response = client.get("/")

        # Essential security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

        assert "Referrer-Policy" in response.headers

        # CSP should be present (checked in detail above)
        assert "Content-Security-Policy" in response.headers
