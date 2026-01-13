"""
Marketing email service for welcome series and subscriber management.

Provides:
- Automated welcome email series (Day 0, Day 3, Day 7)
- Duplicate prevention via welcome_emails_sent table
- Resend Audience sync for campaign management
- Unsubscribe token generation
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import os
import requests
from flask import current_app, has_app_context, url_for
from itsdangerous import URLSafeSerializer


# Email type constants
WELCOME_DAY_0 = "welcome_day0"
WELCOME_DAY_3 = "welcome_day3"
WELCOME_DAY_7 = "welcome_day7"


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


def get_unsubscribe_url(user_id: str) -> str:
    """
    Generate a signed unsubscribe URL for the user.

    Args:
        user_id: User's UUID

    Returns:
        Full unsubscribe URL with signed token
    """
    try:
        secret_key = current_app.secret_key or os.getenv("SECRET_KEY", "dev-secret")
        s = URLSafeSerializer(secret_key, salt="unsubscribe")
        token = s.dumps(user_id)
        return url_for("marketing.unsubscribe", token=token, _external=True)
    except Exception as e:
        _safe_log_error(f"Error generating unsubscribe URL: {e}")
        # Fallback to account settings page
        return url_for("dashboard.account", _external=True)


def verify_unsubscribe_token(token: str) -> Optional[str]:
    """
    Verify an unsubscribe token and return the user_id.

    Args:
        token: Signed token from unsubscribe URL

    Returns:
        user_id if valid, None if invalid/expired
    """
    try:
        secret_key = current_app.secret_key or os.getenv("SECRET_KEY", "dev-secret")
        s = URLSafeSerializer(secret_key, salt="unsubscribe")
        user_id = s.loads(token, max_age=30 * 24 * 60 * 60)  # Valid for 30 days
        return user_id
    except Exception as e:
        _safe_log_error(f"Invalid unsubscribe token: {e}")
        return None


def _get_email_footer(unsubscribe_url: str) -> str:
    """Generate the email footer with unsubscribe link."""
    return f"""
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 24px 40px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0 0 8px; color: #6b7280; font-size: 12px; text-align: center;">
                                You received this because you signed up for PlantCareAI updates.
                            </p>
                            <p style="margin: 0; color: #9ca3af; font-size: 11px; text-align: center;">
                                <a href="{unsubscribe_url}" style="color: #9ca3af; text-decoration: underline;">Unsubscribe</a>
                                from marketing emails
                            </p>
                        </td>
                    </tr>
"""


def _get_welcome_day0_email(unsubscribe_url: str) -> Dict[str, str]:
    """Generate Day 0 welcome email (immediate)."""
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to PlantCareAI!</title>
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
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">Welcome to PlantCareAI!</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 16px; color: #111827; font-size: 20px; font-weight: 600;">You're all set to grow! 🎉</h2>
                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                Thanks for joining PlantCareAI. We're here to help your plants thrive with smart care reminders and AI-powered advice.
                            </p>

                            <h3 style="margin: 24px 0 16px; color: #111827; font-size: 18px; font-weight: 600;">Quick Start Guide</h3>

                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 24px;">
                                <tr>
                                    <td style="padding: 16px; background-color: #ecfdf5; border-radius: 8px; margin-bottom: 12px;">
                                        <p style="margin: 0; color: #065f46; font-size: 14px;">
                                            <strong>1. Add your plants</strong><br>
                                            Snap a photo and tell us what you're growing. We'll help track care schedules.
                                        </p>
                                    </td>
                                </tr>
                                <tr><td style="height: 12px;"></td></tr>
                                <tr>
                                    <td style="padding: 16px; background-color: #f0f9ff; border-radius: 8px; margin-bottom: 12px;">
                                        <p style="margin: 0; color: #1e40af; font-size: 14px;">
                                            <strong>2. Set reminders</strong><br>
                                            Get notified when it's time to water, fertilize, or rotate your plants.
                                        </p>
                                    </td>
                                </tr>
                                <tr><td style="height: 12px;"></td></tr>
                                <tr>
                                    <td style="padding: 16px; background-color: #fef3c7; border-radius: 8px;">
                                        <p style="margin: 0; color: #92400e; font-size: 14px;">
                                            <strong>3. Ask our AI</strong><br>
                                            Got questions? Our plant care AI knows all about watering, light, and troubleshooting.
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0; color: #4b5563; font-size: 14px; line-height: 1.5;">
                                Happy growing! 🌿<br>
                                <em>The PlantCareAI Team</em>
                            </p>
                        </td>
                    </tr>

{_get_email_footer(unsubscribe_url)}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    text_content = """Welcome to PlantCareAI! 🌱

You're all set to grow!

Thanks for joining PlantCareAI. We're here to help your plants thrive with smart care reminders and AI-powered advice.

QUICK START GUIDE:

1. Add your plants
Snap a photo and tell us what you're growing. We'll help track care schedules.

2. Set reminders
Get notified when it's time to water, fertilize, or rotate your plants.

3. Ask our AI
Got questions? Our plant care AI knows all about watering, light, and troubleshooting.

Happy growing! 🌿
The PlantCareAI Team

---
To unsubscribe from marketing emails, visit your account settings.
"""

    return {
        "subject": "Welcome to PlantCareAI! 🌱 Let's grow together",
        "html": html_content,
        "text": text_content
    }


def _get_welcome_day3_email(unsubscribe_url: str) -> Dict[str, str]:
    """Generate Day 3 welcome email (plant care tips)."""
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plant Care Tips from PlantCareAI</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #10b981 0%, #06b6d4 100%); padding: 40px 40px 30px; text-align: center;">
                            <div style="font-size: 48px; margin-bottom: 16px;">💧</div>
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">3 Tips for Happy Plants</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                Here are some expert tips to help your plants flourish:
                            </p>

                            <h3 style="margin: 0 0 12px; color: #111827; font-size: 18px; font-weight: 600;">🌊 Tip #1: Check the soil, not the calendar</h3>
                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 14px; line-height: 1.6;">
                                Instead of watering on a fixed schedule, stick your finger 1-2 inches into the soil. If it's dry, water thoroughly. If moist, wait another day or two. Most houseplant problems come from overwatering!
                            </p>

                            <h3 style="margin: 0 0 12px; color: #111827; font-size: 18px; font-weight: 600;">☀️ Tip #2: Light matters more than you think</h3>
                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 14px; line-height: 1.6;">
                                "Bright indirect light" means near a window but not in direct sun rays. North-facing windows = low light. South-facing = bright. East/West = medium. Match your plants to their light needs!
                            </p>

                            <h3 style="margin: 0 0 12px; color: #111827; font-size: 18px; font-weight: 600;">🔄 Tip #3: Rotate for even growth</h3>
                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 14px; line-height: 1.6;">
                                Give your plants a quarter turn every time you water. This helps them grow evenly instead of leaning toward the light. Your future self will thank you!
                            </p>

                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 24px 0;">
                                <tr>
                                    <td style="background-color: #ecfdf5; border-radius: 8px; padding: 20px; text-align: center;">
                                        <p style="margin: 0 0 8px; color: #065f46; font-size: 14px; font-weight: 600;">
                                            💡 Pro tip: Use our AI assistant for personalized advice
                                        </p>
                                        <p style="margin: 0; color: #047857; font-size: 13px;">
                                            Just ask about your specific plant and we'll help!
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0; color: #4b5563; font-size: 14px; line-height: 1.5;">
                                Keep growing! 🌿<br>
                                <em>The PlantCareAI Team</em>
                            </p>
                        </td>
                    </tr>

{_get_email_footer(unsubscribe_url)}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    text_content = """3 Tips for Happy Plants 💧

Here are some expert tips to help your plants flourish:

TIP #1: Check the soil, not the calendar 🌊
Instead of watering on a fixed schedule, stick your finger 1-2 inches into the soil. If it's dry, water thoroughly. If moist, wait another day or two. Most houseplant problems come from overwatering!

TIP #2: Light matters more than you think ☀️
"Bright indirect light" means near a window but not in direct sun rays. North-facing windows = low light. South-facing = bright. East/West = medium. Match your plants to their light needs!

TIP #3: Rotate for even growth 🔄
Give your plants a quarter turn every time you water. This helps them grow evenly instead of leaning toward the light. Your future self will thank you!

💡 Pro tip: Use our AI assistant for personalized advice about your specific plants!

Keep growing! 🌿
The PlantCareAI Team

---
To unsubscribe from marketing emails, visit your account settings.
"""

    return {
        "subject": "💧 3 simple tips for happier plants",
        "html": html_content,
        "text": text_content
    }


def _get_welcome_day7_email(unsubscribe_url: str) -> Dict[str, str]:
    """Generate Day 7 welcome email (feature highlights)."""
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Get More from PlantCareAI</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #10b981 0%, #06b6d4 100%); padding: 40px 40px 30px; text-align: center;">
                            <div style="font-size: 48px; margin-bottom: 16px;">✨</div>
                            <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">Getting the Most from PlantCareAI</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                Here are some features you might not have discovered yet:
                            </p>

                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 16px;">
                                <tr>
                                    <td style="padding: 20px; background-color: #fef3c7; border-radius: 8px;">
                                        <h3 style="margin: 0 0 8px; color: #92400e; font-size: 16px; font-weight: 600;">🤖 AI Plant Doctor</h3>
                                        <p style="margin: 0; color: #92400e; font-size: 14px; line-height: 1.5;">
                                            Describe symptoms or upload a photo, and our AI will help diagnose issues and suggest solutions. "My pothos has yellow leaves" → instant help!
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 16px;">
                                <tr>
                                    <td style="padding: 20px; background-color: #dbeafe; border-radius: 8px;">
                                        <h3 style="margin: 0 0 8px; color: #1e40af; font-size: 16px; font-weight: 600;">⏰ Smart Reminders</h3>
                                        <p style="margin: 0; color: #1e40af; font-size: 14px; line-height: 1.5;">
                                            Set watering, fertilizing, and repotting reminders. We'll even adjust suggestions based on weather conditions in your area!
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 24px;">
                                <tr>
                                    <td style="padding: 20px; background-color: #ecfdf5; border-radius: 8px;">
                                        <h3 style="margin: 0 0 8px; color: #065f46; font-size: 16px; font-weight: 600;">📔 Plant Journal</h3>
                                        <p style="margin: 0; color: #065f46; font-size: 14px; line-height: 1.5;">
                                            Track your plant's progress with photos and notes. Perfect for spotting patterns and celebrating growth milestones!
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 14px; line-height: 1.5;">
                                Have questions or feedback? Just reply to this email — we'd love to hear from you!
                            </p>

                            <p style="margin: 0; color: #4b5563; font-size: 14px; line-height: 1.5;">
                                Happy planting! 🌿<br>
                                <em>The PlantCareAI Team</em>
                            </p>
                        </td>
                    </tr>

{_get_email_footer(unsubscribe_url)}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    text_content = """Getting the Most from PlantCareAI ✨

Here are some features you might not have discovered yet:

🤖 AI PLANT DOCTOR
Describe symptoms or upload a photo, and our AI will help diagnose issues and suggest solutions. "My pothos has yellow leaves" → instant help!

⏰ SMART REMINDERS
Set watering, fertilizing, and repotting reminders. We'll even adjust suggestions based on weather conditions in your area!

📔 PLANT JOURNAL
Track your plant's progress with photos and notes. Perfect for spotting patterns and celebrating growth milestones!

Have questions or feedback? Just reply to this email — we'd love to hear from you!

Happy planting! 🌿
The PlantCareAI Team

---
To unsubscribe from marketing emails, visit your account settings.
"""

    return {
        "subject": "✨ Features you might have missed",
        "html": html_content,
        "text": text_content
    }


def send_welcome_email(
    user_id: str, email: str, email_type: str
) -> Dict[str, Any]:
    """
    Send a welcome email and record it to prevent duplicates.

    Args:
        user_id: User's UUID
        email: User's email address
        email_type: One of WELCOME_DAY_0, WELCOME_DAY_3, WELCOME_DAY_7

    Returns:
        Dict with 'success' bool and 'message' or 'error'
    """
    from app.services import supabase_client

    # Check if already sent
    try:
        client = supabase_client._supabase_client
        if not client:
            return {"success": False, "error": "database_not_configured"}

        existing = (
            client.table("welcome_emails_sent")
            .select("id")
            .eq("user_id", user_id)
            .eq("email_type", email_type)
            .execute()
        )

        if existing.data:
            _safe_log_info(f"Welcome email {email_type} already sent to {user_id}")
            return {"success": True, "message": "already_sent"}

    except Exception as e:
        _safe_log_error(f"Error checking welcome email history: {e}")
        # Continue anyway - we'll try to insert and let the unique constraint catch duplicates

    # Get API key
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        _safe_log_error("RESEND_API_KEY not configured")
        return {"success": False, "error": "email_not_configured"}

    # Generate unsubscribe URL
    unsubscribe_url = get_unsubscribe_url(user_id)

    # Get email content based on type
    if email_type == WELCOME_DAY_0:
        email_content = _get_welcome_day0_email(unsubscribe_url)
    elif email_type == WELCOME_DAY_3:
        email_content = _get_welcome_day3_email(unsubscribe_url)
    elif email_type == WELCOME_DAY_7:
        email_content = _get_welcome_day7_email(unsubscribe_url)
    else:
        return {"success": False, "error": f"unknown_email_type: {email_type}"}

    # Send email via Resend API
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": "PlantCareAI <hello@send.plantcareai.app>",
                "to": [email],
                "subject": email_content["subject"],
                "html": email_content["html"],
                "text": email_content["text"],
            },
            timeout=10,
        )

        if response.status_code == 200:
            # Record that we sent the email
            try:
                client.table("welcome_emails_sent").insert(
                    {"user_id": user_id, "email_type": email_type}
                ).execute()
            except Exception as e:
                # If insert fails due to duplicate, that's fine
                if "duplicate key" not in str(e) and "23505" not in str(e):
                    _safe_log_error(f"Error recording welcome email: {e}")

            _safe_log_info(f"Welcome email {email_type} sent to {email}")
            return {"success": True, "message": "sent"}
        else:
            error_data = response.json() if response.text else {}
            error_message = error_data.get("message", "Unknown error")
            _safe_log_error(f"Resend API error: {response.status_code} - {error_message}")
            return {"success": False, "error": "email_send_failed"}

    except requests.exceptions.Timeout:
        _safe_log_error("Resend API timeout for welcome email")
        return {"success": False, "error": "timeout"}
    except Exception as e:
        _safe_log_error(f"Error sending welcome email: {e}")
        return {"success": False, "error": str(e)}


def get_pending_welcome_emails() -> List[Dict[str, Any]]:
    """
    Get users who are due for welcome emails.

    Returns list of dicts with user_id, email, and email_type needed.
    """
    from app.services import supabase_client

    pending = []
    now = datetime.now(timezone.utc)

    try:
        client = supabase_client._supabase_client
        if not client:
            return pending

        # Get all users with marketing_opt_in = True
        result = client.table("profiles").select(
            "id, email, marketing_opt_in, created_at"
        ).eq("marketing_opt_in", True).execute()

        if not result.data:
            return pending

        # Get all welcome emails already sent
        sent_result = client.table("welcome_emails_sent").select(
            "user_id, email_type"
        ).execute()

        sent_emails = set()
        if sent_result.data:
            for row in sent_result.data:
                sent_emails.add((row["user_id"], row["email_type"]))

        # Check each user for pending emails
        for user in result.data:
            user_id = user["id"]
            email = user.get("email")
            created_at_str = user.get("created_at")

            if not email or not created_at_str:
                continue

            # Parse created_at
            try:
                created_at = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                continue

            days_since_signup = (now - created_at).days

            # Day 0: Send immediately if not sent
            if (user_id, WELCOME_DAY_0) not in sent_emails:
                pending.append({
                    "user_id": user_id,
                    "email": email,
                    "email_type": WELCOME_DAY_0,
                })

            # Day 3: Send after 3 days if not sent
            if days_since_signup >= 3 and (user_id, WELCOME_DAY_3) not in sent_emails:
                pending.append({
                    "user_id": user_id,
                    "email": email,
                    "email_type": WELCOME_DAY_3,
                })

            # Day 7: Send after 7 days if not sent
            if days_since_signup >= 7 and (user_id, WELCOME_DAY_7) not in sent_emails:
                pending.append({
                    "user_id": user_id,
                    "email": email,
                    "email_type": WELCOME_DAY_7,
                })

    except Exception as e:
        _safe_log_error(f"Error getting pending welcome emails: {e}")

    return pending


def process_welcome_email_queue() -> Dict[str, Any]:
    """
    Process all pending welcome emails.

    Called by the scheduler to send welcome emails in batches.

    Returns:
        Dict with counts of sent, failed, and skipped emails
    """
    stats = {"sent": 0, "failed": 0, "skipped": 0}

    try:
        pending = get_pending_welcome_emails()
        _safe_log_info(f"Processing {len(pending)} pending welcome emails")

        for item in pending:
            result = send_welcome_email(
                item["user_id"], item["email"], item["email_type"]
            )

            if result.get("success"):
                if result.get("message") == "already_sent":
                    stats["skipped"] += 1
                else:
                    stats["sent"] += 1
            else:
                stats["failed"] += 1

    except Exception as e:
        _safe_log_error(f"Error processing welcome email queue: {e}")

    _safe_log_info(
        f"Welcome email queue processed: {stats['sent']} sent, "
        f"{stats['failed']} failed, {stats['skipped']} skipped"
    )
    return stats


def sync_to_resend_audience(email: str, subscribed: bool) -> bool:
    """
    Sync a contact to/from the Resend Audience for campaign management.

    Args:
        email: User's email address
        subscribed: True to add, False to remove

    Returns:
        True if successful, False otherwise
    """
    api_key = os.getenv("RESEND_API_KEY")
    audience_id = os.getenv("RESEND_AUDIENCE_ID")

    if not api_key or not audience_id:
        _safe_log_info("Resend Audience not configured, skipping sync")
        return True  # Not an error, just not configured

    try:
        if subscribed:
            # Add contact to audience
            response = requests.post(
                f"https://api.resend.com/audiences/{audience_id}/contacts",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"email": email},
                timeout=10,
            )
        else:
            # Remove contact from audience
            response = requests.delete(
                f"https://api.resend.com/audiences/{audience_id}/contacts/{email}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )

        if response.status_code in (200, 201, 204):
            action = "added to" if subscribed else "removed from"
            _safe_log_info(f"Contact {email} {action} Resend Audience")
            return True
        else:
            _safe_log_error(
                f"Resend Audience sync failed: {response.status_code} - {response.text}"
            )
            return False

    except Exception as e:
        _safe_log_error(f"Error syncing to Resend Audience: {e}")
        return False
