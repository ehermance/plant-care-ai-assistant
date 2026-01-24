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
  <title>PlantCareAI Verification Code</title>
</head>
<body style="margin:0; padding:0; background-color:#ffffff; font-family:Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
    <tr>
      <td align="center" style="padding:24px;">
        <table width="600" cellpadding="0" cellspacing="0" role="presentation" style="width:100%; max-width:600px;">
          <tr>
            <td style="padding:0 0 16px; font-size:18px; font-weight:bold; color:#111827;">
              PlantCareAI
            </td>
          </tr>

          <tr>
            <td style="padding:0 0 12px; font-size:16px; font-weight:bold; color:#111827;">
              Your verification code
            </td>
          </tr>

          <tr>
            <td style="padding:0 0 16px; font-size:14px; color:#44403c; line-height:1.5;">
              Enter this code to sign in:
            </td>
          </tr>

          <tr>
            <td style="padding:16px; border:1px solid #e8e3dd; border-radius:6px; text-align:center;">
              <div style="font-size:32px; font-weight:bold; letter-spacing:4px; color:#111827;">
                {code}
              </div>
            </td>
          </tr>

          <tr>
            <td style="padding:16px 0 0; font-size:13px; color:#78716c; line-height:1.5;">
              This code expires in 15 minutes. Don’t share it with anyone.
            </td>
          </tr>

          <tr>
            <td style="padding:16px 0 0; font-size:13px; color:#78716c; line-height:1.5;">
              If you didn’t request this, you can safely ignore this email.
            </td>
          </tr>

          <tr>
            <td style="padding:24px 0 0; font-size:12px; color:#a69d91; line-height:1.5;">
              Automated message from PlantCareAI.
              Need help? support@plantcareai.app
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
    text_content = f"""PlantCareAI
    
Your verification code

Enter this code to sign in:
{code}

This code expires in 15 minutes. Don’t share it with anyone.

If you didn’t request this, you can safely ignore this email.

---
Automated message from PlantCareAI.
Need help? support@plantcareai.app
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
                "from": "PlantCareAI <verify@updates.plantcareai.app>",
                "to": [email],
                "subject": "Your PlantCareAI verification code is ready",
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
