"""
Test script to send all marketing emails to admin accounts.

Usage: python test_emails.py

This script:
1. Queries admin users from the database (is_admin = true)
2. Uses the marketing_emails.py service to send test emails
3. Prepends "[TEST]" to all subject lines
"""

import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the app to the path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.services.marketing_emails import (
    # Email type constants
    WELCOME_DAY_0,
    WELCOME_DAY_3,
    WELCOME_DAY_7,
    WELCOME_DAY_10,
    REENGAGEMENT_14DAY,
    SEASONAL_SPRING,
    SEASONAL_SUMMER,
    SEASONAL_FALL,
    SEASONAL_WINTER,
    MILESTONE_FIRST_PLANT,
    MILESTONE_ANNIVERSARY_30,
    MILESTONE_STREAK_5,
    MILESTONE_COLLECTION_5,
    # Email content generators
    _get_welcome_day0_email,
    _get_welcome_day3_email,
    _get_welcome_day7_email,
    _get_welcome_day10_email,
    _get_reengagement_14day_email,
    _get_seasonal_spring_email,
    _get_seasonal_summer_email,
    _get_seasonal_fall_email,
    _get_seasonal_winter_email,
    _get_milestone_first_plant_email,
    _get_milestone_anniversary_30_email,
    _get_milestone_streak_5_email,
    _get_milestone_collection_5_email,
)

# Placeholder unsubscribe URL (no Flask context available)
UNSUBSCRIBE_URL = "https://plantcareai.app/unsubscribe?token=test-token"


def get_admin_emails() -> list[str]:
    """
    Query Supabase for admin users and return their email addresses.

    Returns:
        List of email addresses for admin users
    """
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not service_key:
        print("\n[ERROR] SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured")
        return []

    try:
        client = create_client(url, service_key)
        result = client.table("profiles").select("email").eq("is_admin", True).execute()

        if result.data:
            emails = [row["email"] for row in result.data if row.get("email")]
            return emails
        return []
    except Exception as e:
        print(f"\n[ERROR] Failed to query admin users: {e}")
        return []


def get_all_test_emails() -> list[tuple[str, str, dict]]:
    """
    Generate all marketing email types for testing.

    Returns:
        List of tuples: (email_type_name, display_name, email_content_dict)
    """
    return [
        # Welcome series
        (WELCOME_DAY_0, "Welcome Day 0", _get_welcome_day0_email(UNSUBSCRIBE_URL)),
        (WELCOME_DAY_3, "Welcome Day 3", _get_welcome_day3_email(UNSUBSCRIBE_URL)),
        (WELCOME_DAY_7, "Welcome Day 7 (Weather)", _get_welcome_day7_email(UNSUBSCRIBE_URL)),
        (WELCOME_DAY_10, "Welcome Day 10 (Journal)", _get_welcome_day10_email(UNSUBSCRIBE_URL)),

        # Re-engagement
        (REENGAGEMENT_14DAY, "Re-engagement (14 days)", _get_reengagement_14day_email(UNSUBSCRIBE_URL)),

        # Seasonal emails
        (SEASONAL_SPRING, "Seasonal: Spring", _get_seasonal_spring_email(UNSUBSCRIBE_URL)),
        (SEASONAL_SUMMER, "Seasonal: Summer", _get_seasonal_summer_email(UNSUBSCRIBE_URL)),
        (SEASONAL_FALL, "Seasonal: Fall", _get_seasonal_fall_email(UNSUBSCRIBE_URL)),
        (SEASONAL_WINTER, "Seasonal: Winter", _get_seasonal_winter_email(UNSUBSCRIBE_URL)),

        # Milestone emails
        (MILESTONE_FIRST_PLANT, "Milestone: First Plant", _get_milestone_first_plant_email(UNSUBSCRIBE_URL)),
        (MILESTONE_ANNIVERSARY_30, "Milestone: 30-day Anniversary", _get_milestone_anniversary_30_email(UNSUBSCRIBE_URL, "Test Plant")),
        (MILESTONE_STREAK_5, "Milestone: 5-day Streak", _get_milestone_streak_5_email(UNSUBSCRIBE_URL, 5)),
        (MILESTONE_COLLECTION_5, "Milestone: 5 Plants", _get_milestone_collection_5_email(UNSUBSCRIBE_URL, 5)),
    ]


def send_test_email(to_email: str, email_type: str, display_name: str, email_content: dict) -> bool:
    """
    Send a single test email via Resend API.

    Args:
        to_email: Recipient email address
        email_type: Email type constant (for logging)
        display_name: Human-readable name for logging
        email_content: Dict with 'subject', 'html', 'text' keys

    Returns:
        True if sent successfully, False otherwise
    """
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print(f"   [SKIP] {display_name} - RESEND_API_KEY not configured")
        return False

    try:
        # Prepend [TEST] to subject line
        subject = f"[TEST] {email_content['subject']}"

        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": "Ellen from PlantCareAI <hello@updates.plantcareai.app>",
                "to": [to_email],
                "subject": subject,
                "html": email_content["html"],
                "text": email_content.get("text", ""),
                "reply_to": "support@plantcareai.app",
                "headers": {
                    "List-Unsubscribe": f"<{UNSUBSCRIBE_URL}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
                },
                "tracking": {
                    "click": False,
                    "open": False
                }
            },
            timeout=10,
        )

        if response.status_code == 200:
            print(f"   [OK] {display_name}")
            return True
        else:
            error = response.json().get("message", response.text)
            print(f"   [FAIL] {display_name}: {error}")
            return False

    except Exception as e:
        print(f"   [FAIL] {display_name}: {e}")
        return False


def save_previews():
    """Save HTML previews to email_previews directory."""
    preview_dir = Path("email_previews")
    preview_dir.mkdir(exist_ok=True)

    all_emails = get_all_test_emails()

    print("\n[*] Saving HTML previews...")
    for email_type, display_name, email_content in all_emails:
        filename = f"{email_type}.html"
        filepath = preview_dir / filename
        filepath.write_text(email_content["html"], encoding="utf-8")
        print(f"   [OK] {filepath}")

    print(f"\n   Open these files in your browser to preview the designs.")


def send_all_emails():
    """Send all marketing emails to admin accounts."""
    admin_emails = get_admin_emails()

    if not admin_emails:
        print("\n[ERROR] No admin users found. Make sure is_admin=true for at least one user.")
        return

    print(f"\n[*] Found {len(admin_emails)} admin account(s):")
    for email in admin_emails:
        print(f"   - {email}")

    all_emails = get_all_test_emails()

    total_sent = 0
    total_failed = 0

    for admin_email in admin_emails:
        print(f"\n[*] Sending {len(all_emails)} test emails to {admin_email}...")

        for i, (email_type, display_name, email_content) in enumerate(all_emails):
            if send_test_email(admin_email, email_type, display_name, email_content):
                total_sent += 1
            else:
                total_failed += 1
            # Rate limit: Resend allows 2 requests/second, so wait 0.6s between emails
            if i < len(all_emails) - 1:
                time.sleep(0.6)

    print(f"\n[*] Results: {total_sent} sent, {total_failed} failed")
    print("\n   Check your inbox for the test emails!")


def main():
    """Main entry point."""
    print("=" * 60)
    print("   PlantCareAI Marketing Email Test Suite")
    print("=" * 60)

    # Check for required environment variables
    missing_vars = []
    if not os.getenv("RESEND_API_KEY"):
        missing_vars.append("RESEND_API_KEY")
    if not os.getenv("SUPABASE_URL"):
        missing_vars.append("SUPABASE_URL")
    if not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        missing_vars.append("SUPABASE_SERVICE_ROLE_KEY")

    if missing_vars:
        print(f"\n[WARNING] Missing environment variables: {', '.join(missing_vars)}")
        print("   Some features may not work correctly.")

    print("\n[*] Available email types:")
    all_emails = get_all_test_emails()
    for i, (email_type, display_name, _) in enumerate(all_emails, 1):
        print(f"   {i:2}. {display_name}")

    # Save previews
    save_previews()

    # Send emails to admins
    send_all_emails()

    print("\n[DONE] Complete!")


if __name__ == "__main__":
    main()
