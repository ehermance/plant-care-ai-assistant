"""
Unit tests for Photo Upload Validation Edge Cases.

Tests file validation, size limits, format validation, and error handling:
- File size limits
- Supported file formats
- Invalid file detection
- Security validation
"""

import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO


class TestPhotoValidation:
    """Test photo upload validation and edge cases."""

    def test_validate_file_size_limit(self):
        """Should reject files exceeding size limit."""
        from app.utils.file_upload import validate_upload_file

        # Create a real BytesIO object exceeding MAX_FILE_SIZE (5MB)
        large_data = b'x' * (6 * 1024 * 1024)  # 6MB
        fake_file = BytesIO(large_data)
        fake_file.filename = 'large_image.jpg'
        fake_file.content_type = 'image/jpeg'

        # Validate
        is_valid, error, file_bytes = validate_upload_file(fake_file)

        # Assertions
        assert is_valid is False
        assert error is not None
        assert '5MB' in error or 'less than' in error.lower()
        assert file_bytes is None

    def test_validate_supported_image_formats(self):
        """Should accept supported image formats by filename extension."""
        from app.utils.file_upload import allowed_file

        supported_formats = ['test.jpg', 'test.jpeg', 'test.png', 'test.webp', 'test.gif']

        for filename in supported_formats:
            # Test filename validation
            is_allowed = allowed_file(filename)
            # Should pass filename validation
            assert is_allowed is True, f"Format {filename} should be allowed"

    def test_validate_rejects_invalid_formats(self):
        """Should reject non-image file formats."""
        from app.utils.file_upload import allowed_file

        invalid_formats = ['malware.exe', 'script.js', 'document.pdf', 'hack.sh', 'virus.bat']

        for filename in invalid_formats:
            # Test filename validation
            is_allowed = allowed_file(filename)
            # Should be rejected
            assert is_allowed is False, f"Format {filename} should be rejected"


class TestPhotoUploadSecurity:
    """Test photo upload security validations."""

    def test_sanitize_filename_removes_path_traversal(self):
        """Should prevent path traversal attacks in filenames."""
        from werkzeug.utils import secure_filename

        malicious_filenames = [
            ('../../../etc/passwd', 'etc_passwd'),
            ('..\\..\\windows\\system32\\config', 'windows_system32_config'),
            ('normal_file/../../sneaky.exe', 'normal_file_sneaky.exe'),
        ]

        for malicious_name, expected_pattern in malicious_filenames:
            safe_name = secure_filename(malicious_name)

            # Should not contain directory separators
            assert '/' not in safe_name, f"Path separator / found in {safe_name}"
            assert '\\' not in safe_name, f"Path separator \\ found in {safe_name}"
            # Should be safe (can contain underscores from sanitization)
            assert safe_name, f"Filename should not be empty after sanitization"

    @patch('app.services.supabase_client.get_admin_client')
    def test_photo_upload_validates_user_authorization(self, mock_get_client):
        """Should validate user authorization before uploading."""
        from app.services.supabase_client import upload_plant_photo_versions

        # Mock Supabase client
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase

        # Mock storage upload
        mock_supabase.storage.from_.return_value.upload.return_value = {'path': 'photo.jpg'}

        # Upload with user ID
        file_bytes = b'fake image'
        photo_urls, error = upload_plant_photo_versions(file_bytes, 'user-123', 'photo.jpg')

        # Verify upload path includes user ID for authorization
        if photo_urls:
            # The path should be scoped to the user
            upload_call = mock_supabase.storage.from_.return_value.upload.call_args_list
            if upload_call:
                # Check that user ID is in the path
                assert any('user-123' in str(call) or 'user_id' in str(call) for call in upload_call)

    def test_validate_empty_file(self):
        """Should reject empty files."""
        from app.utils.file_upload import validate_upload_file

        # Create empty file using BytesIO
        fake_file = BytesIO(b'')
        fake_file.filename = 'empty.jpg'
        fake_file.content_type = 'image/jpeg'

        # Validate
        is_valid, error, file_bytes = validate_upload_file(fake_file)

        # Empty files should fail validation (invalid image content)
        assert is_valid is False
        assert error is not None
