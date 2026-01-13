"""
Test script to preview and send welcome emails.

Usage: python test_emails.py
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test email address
TEST_EMAIL = "ellen.diep+marketing_emails@gmail.com"

# Placeholder unsubscribe URL (no Flask context available)
UNSUBSCRIBE_URL = "https://plantcareai.app/unsubscribe?token=test-token"


def get_email_footer(unsubscribe_url: str) -> str:
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


def get_welcome_day0_email(unsubscribe_url: str) -> dict:
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

{get_email_footer(unsubscribe_url)}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    return {
        "subject": "Welcome to PlantCareAI! 🌱 Let's grow together",
        "html": html_content,
    }


def get_welcome_day3_email(unsubscribe_url: str) -> dict:
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

{get_email_footer(unsubscribe_url)}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    return {
        "subject": "💧 3 simple tips for happier plants",
        "html": html_content,
    }


def get_welcome_day7_email(unsubscribe_url: str) -> dict:
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

{get_email_footer(unsubscribe_url)}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    return {
        "subject": "✨ Features you might have missed",
        "html": html_content,
    }


def save_previews():
    """Save HTML previews to files."""
    preview_dir = Path("email_previews")
    preview_dir.mkdir(exist_ok=True)

    emails = [
        ("welcome_day0.html", get_welcome_day0_email(UNSUBSCRIBE_URL)),
        ("welcome_day3.html", get_welcome_day3_email(UNSUBSCRIBE_URL)),
        ("welcome_day7.html", get_welcome_day7_email(UNSUBSCRIBE_URL)),
    ]

    print("\n[*] Saving HTML previews...")
    for filename, email in emails:
        filepath = preview_dir / filename
        filepath.write_text(email["html"], encoding="utf-8")
        print(f"   [OK] {filepath}")

    print(f"\n   Open these files in your browser to preview the designs.")


def send_emails():
    """Send all 3 emails via Resend API."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("\n[ERROR] RESEND_API_KEY not found in .env file")
        return

    emails = [
        ("Day 0 - Welcome", get_welcome_day0_email(UNSUBSCRIBE_URL)),
        ("Day 3 - Tips", get_welcome_day3_email(UNSUBSCRIBE_URL)),
        ("Day 7 - Features", get_welcome_day7_email(UNSUBSCRIBE_URL)),
    ]

    print(f"\n[*] Sending emails to {TEST_EMAIL}...")

    for name, email in emails:
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": "Ellen from PlantCareAI <hello@updates.plantcareai.app>",
                    "to": [TEST_EMAIL],
                    "subject": f"[TEST] {email['subject']}",
                    "html": email["html"],
                },
                timeout=10,
            )

            if response.status_code == 200:
                print(f"   [OK] {name} sent successfully")
            else:
                error = response.json().get("message", response.text)
                print(f"   [FAIL] {name} failed: {error}")

        except Exception as e:
            print(f"   [FAIL] {name} failed: {e}")

    print("\n   Check your inbox!")


if __name__ == "__main__":
    print("=" * 50)
    print("   PlantCareAI Welcome Email Tester")
    print("=" * 50)

    save_previews()
    send_emails()

    print("\n[DONE] Complete!")
