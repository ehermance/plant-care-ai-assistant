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
from app.utils.sanitize import mask_email as _mask_email


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
            _safe_log_info(f"OTP email sent successfully to {_mask_email(email)}")
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
                "message": "Our email service is temporarily unavailable. Please try again in a few minutes."
            }

    except requests.exceptions.Timeout:
        _safe_log_error("Resend API timeout")
        return {
            "success": False,
            "error": "timeout",
            "message": "Our email service is temporarily unavailable. Please try again in a few minutes."
        }
    except requests.exceptions.ConnectionError:
        _safe_log_error("Resend API connection error (service may be down)")
        return {
            "success": False,
            "error": "service_unavailable",
            "message": "Our email service is temporarily unavailable. Please try again in a few minutes."
        }
    except Exception as e:
        _safe_log_error(f"Error sending email via Resend: {e}")
        return {
            "success": False,
            "error": "unknown",
            "message": "Unable to send email right now. Please try again later."
        }


def send_legal_update_email(email: str) -> Dict[str, Any]:
    """
    Send a transactional notification about material ToS/Privacy Policy changes.

    This is a service notification (not marketing), so it does NOT check
    MARKETING_EMAILS_ENABLED and is always allowed.

    Args:
        email: Recipient email address

    Returns:
        Dict with 'success' bool and 'message' or 'error'
    """
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        _safe_log_error("RESEND_API_KEY not configured")
        return {
            "success": False,
            "error": "email_not_configured",
            "message": "Email service not configured"
        }

    app_url = os.getenv("APP_URL", "https://plantcareai.app")

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PlantCareAI - I've Updated Our AI Provider</title>
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
            <td style="padding:0 0 16px; font-size:14px; color:#44403c; line-height:1.6;">
              Hi there,
            </td>
          </tr>

          <tr>
            <td style="padding:0 0 16px; font-size:14px; color:#44403c; line-height:1.6;">
              I've made a change to how PlantCareAI generates your plant care advice. I've switched
              the AI provider from OpenAI to <strong>Anthropic Claude</strong> &mdash; the company behind Claude AI.
            </td>
          </tr>

          <tr>
            <td style="padding:0 0 16px; font-size:14px; color:#44403c; line-height:1.8;">
              <strong>What changed:</strong><br>
              &bull; Your plant questions are now processed by Anthropic's Claude instead of OpenAI's GPT<br>
              &bull; The Privacy Policy has been updated to reflect Anthropic as a data processor
            </td>
          </tr>

          <tr>
            <td style="padding:0 0 16px; font-size:14px; color:#44403c; line-height:1.8;">
              <strong>What didn't change:</strong><br>
              &bull; The advice quality and personalization you're used to<br>
              &bull; How your data is handled (encrypted in transit, not used to train AI models)<br>
              &bull; All other features work exactly the same
            </td>
          </tr>

          <tr>
            <td style="padding:0 0 16px; font-size:14px; color:#44403c; line-height:1.6;">
              <strong>Why I switched:</strong><br>
              I believe in partnering with AI companies whose values align with mine.
              Anthropic's commitment to AI safety made them the right choice for PlantCareAI.
            </td>
          </tr>

          <tr>
            <td style="padding:0 0 16px; font-size:14px; color:#44403c; line-height:1.6;">
              This migration also lets me continue improving the advice quality and accuracy you
              receive &mdash; I'll be refining PlantCareAI's prompts and context to take full
              advantage of Claude's strengths.
            </td>
          </tr>

          <tr>
            <td style="padding:16px; border:1px solid #e8e3dd; border-radius:6px; text-align:center;">
              <a href="{app_url}/privacy" style="display:inline-block; padding:10px 24px; background-color:#059669; color:#ffffff; text-decoration:none; border-radius:6px; font-weight:bold; font-size:14px;">
                Review Updated Privacy Policy
              </a>
            </td>
          </tr>

          <tr>
            <td style="padding:16px 0 0; font-size:14px; color:#44403c; line-height:1.5;">
              When you next log in, you'll see a brief notice asking you to acknowledge the update.
            </td>
          </tr>

          <tr>
            <td style="padding:16px 0 0; font-size:14px; color:#44403c; line-height:1.5;">
              Thanks for being part of PlantCareAI!
            </td>
          </tr>

          <tr>
            <td style="padding:8px 0 0; font-size:14px; color:#44403c; line-height:1.5;">
              &mdash; Ellen
            </td>
          </tr>

          <tr>
            <td style="padding:24px 0 0; font-size:12px; color:#a69d91; line-height:1.5;">
              This is a service notification about changes to PlantCareAI's data processing.
              You are receiving this because you have a PlantCareAI account.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    text_content = f"""PlantCareAI

Hi there,

I've made a change to how PlantCareAI generates your plant care advice. I've switched the AI provider from OpenAI to Anthropic Claude -- the company behind Claude AI.

What changed:
- Your plant questions are now processed by Anthropic's Claude instead of OpenAI's GPT
- The Privacy Policy has been updated to reflect Anthropic as a data processor

What didn't change:
- The advice quality and personalization you're used to
- How your data is handled (encrypted in transit, not used to train AI models)
- All other features work exactly the same

Why I switched:
I believe in partnering with AI companies whose values align with mine. Anthropic's commitment to AI safety made them the right choice for PlantCareAI.

This migration also lets me continue improving the advice quality and accuracy you receive -- I'll be refining PlantCareAI's prompts and context to take full advantage of Claude's strengths.

Review the updated Privacy Policy: {app_url}/privacy

When you next log in, you'll see a brief notice asking you to acknowledge the update.

Thanks for being part of PlantCareAI!

-- Ellen

---
This is a service notification about changes to PlantCareAI's data processing.
You are receiving this because you have a PlantCareAI account.
"""

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": "PlantCareAI <hello@updates.plantcareai.app>",
                "to": [email],
                "subject": "I've updated PlantCareAI's AI provider \u2014 your data stays safe",
                "html": html_content,
                "text": text_content,
            },
            timeout=10
        )

        if response.status_code in (200, 201):
            _safe_log_info(f"Legal update email sent to {_mask_email(email)}")
            return {"success": True, "message": "Legal update email sent"}
        else:
            error_data = response.json() if response.text else {}
            error_message = error_data.get("message", "Unknown error")
            _safe_log_error(f"Resend API error: {response.status_code} - {error_message}")

            if response.status_code == 429:
                return {
                    "success": False,
                    "error": "rate_limit",
                    "message": "Rate limited. Please wait and retry."
                }

            return {
                "success": False,
                "error": "email_send_failed",
                "message": "Our email service is temporarily unavailable. Please try again in a few minutes."
            }

    except requests.exceptions.Timeout:
        _safe_log_error("Resend API timeout sending legal update email")
        return {"success": False, "error": "timeout", "message": "Our email service is temporarily unavailable. Please try again in a few minutes."}
    except requests.exceptions.ConnectionError:
        _safe_log_error("Resend API connection error sending legal update email (service may be down)")
        return {"success": False, "error": "service_unavailable", "message": "Our email service is temporarily unavailable. Please try again in a few minutes."}
    except Exception as e:
        _safe_log_error(f"Error sending legal update email: {e}")
        return {"success": False, "error": "unknown", "message": "Unable to send email right now. Please try again later."}
