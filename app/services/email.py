"""
Email service using Resend for transactional emails.

Provides:
- OTP verification code emails
- Future: Welcome emails, reminder notifications, etc.
"""

from __future__ import annotations
from typing import Dict, Any
import os
import requests
from flask import current_app, has_app_context


def _safe_log_error(message: str) -> None:
    """Log error message only if Flask app context is available."""
    try:
        if has_app_context():
            current_app.logger.error(message)
    except (ImportError, RuntimeError):
        pass


def _safe_log_info(message: str) -> None:
    """Log info message only if Flask app context is available."""
    try:
        if has_app_context():
            current_app.logger.info(message)
    except (ImportError, RuntimeError):
        pass


def send_otp_email(email: str, code: str) -> Dict[str, Any]:
    """
    Send OTP verification code via Resend.

    Args:
        email: Recipient email address
        code: 6-digit OTP code

    Returns:
        Dict with 'success' bool and 'message' or 'error'
    """
    # Get API key from environment
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        _safe_log_error("RESEND_API_KEY not configured")
        return {
            "success": False,
            "error": "email_not_configured",
            "message": "Email service not configured"
        }

    # Prepare email HTML (clean, simple design)
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your PlantCareAI Verification Code</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #10b981 0%, #06b6d4 100%); padding: 40px 40px 30px; text-align: center;">
                            <div style="font-size: 48px; margin-bottom: 16px;">🌱</div>
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">PlantCareAI</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 16px; color: #111827; font-size: 20px; font-weight: 600;">Your Verification Code</h2>
                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.5;">
                                Enter this code to sign in to your PlantCareAI account:
                            </p>

                            <!-- OTP Code Box -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 24px;">
                                <tr>
                                    <td align="center" style="background-color: #f9fafb; border: 2px solid #10b981; border-radius: 8px; padding: 24px;">
                                        <div style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #111827; font-family: 'Courier New', monospace;">
                                            {code}
                                        </div>
                                    </td>
                                </tr>
                            </table>

                            <!-- Warning Box -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 24px;">
                                <tr>
                                    <td style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px; border-radius: 4px;">
                                        <p style="margin: 0; color: #92400e; font-size: 14px; font-weight: 600;">
                                            ⚠️ Code expires in 5 minutes
                                        </p>
                                        <p style="margin: 8px 0 0; color: #92400e; font-size: 13px;">
                                            For your security, this code will expire soon. If it expires, you can request a new one.
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 16px; color: #4b5563; font-size: 14px; line-height: 1.5;">
                                If you didn't request this code, you can safely ignore this email. Someone may have entered your email address by mistake.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 24px 40px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0 0 8px; color: #6b7280; font-size: 12px; text-align: center;">
                                This is an automated message from PlantCareAI
                            </p>
                            <p style="margin: 0; color: #9ca3af; font-size: 11px; text-align: center;">
                                Free plant care tracking and AI-powered gardening tips
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    # Plain text version (for email clients that don't support HTML)
    text_content = f"""PlantCareAI Verification Code

Your verification code is: {code}

This code expires in 5 minutes.

Enter this code to sign in to your PlantCareAI account.

If you didn't request this code, you can safely ignore this email.

---
PlantCareAI - Free plant care tracking and AI-powered gardening tips
"""

    # Send email via Resend API
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": "PlantCareAI <hello@send.plantcareai.app>",
                "to": [email],
                "subject": f"Your PlantCareAI verification code: {code}",
                "html": html_content,
                "text": text_content,
            },
            timeout=10
        )

        if response.status_code == 200:
            _safe_log_info(f"OTP email sent successfully to {email}")
            return {
                "success": True,
                "message": f"Verification code sent to {email}"
            }
        else:
            error_data = response.json() if response.text else {}
            error_message = error_data.get("message", "Unknown error")
            _safe_log_error(f"Resend API error: {response.status_code} - {error_message}")

            # Check for rate limiting
            if response.status_code == 429:
                return {
                    "success": False,
                    "error": "rate_limit",
                    "message": "Too many emails sent. Please wait a few minutes and try again."
                }

            return {
                "success": False,
                "error": "email_send_failed",
                "message": "Failed to send verification email. Please try again."
            }

    except requests.exceptions.Timeout:
        _safe_log_error("Resend API timeout")
        return {
            "success": False,
            "error": "timeout",
            "message": "Email service timed out. Please try again."
        }
    except Exception as e:
        _safe_log_error(f"Error sending email via Resend: {e}")
        return {
            "success": False,
            "error": "unknown",
            "message": "Failed to send verification email. Please try again later."
        }
