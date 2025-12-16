# tests/test_single_user.py
"""
Manual test for weather adjustments for a single user.

This test requires interactive input (email, city) and is skipped by pytest.
Run from project root with: python -m tests.test_single_user
Or: python tests/test_single_user.py

Options:
  --reset  Clear all existing weather adjustments before re-evaluating
"""
import sys
from pathlib import Path

# Add project root to path when running directly
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

import pytest

# Skip this test in pytest - it requires manual input
pytestmark = pytest.mark.skip(reason="Requires manual user input for email and city")


def clear_weather_adjustments(supabase, user_id):
    """Clear all weather adjustments for a user's reminders."""
    result = supabase.table("reminders").update({
        "weather_adjusted_due": None,
        "weather_adjustment_reason": None
    }).eq("user_id", user_id).eq("is_active", True).execute()

    return len(result.data) if result.data else 0


def run_manual_test():
    """Run the manual weather adjustment test."""
    from app import create_app
    from app.services import supabase_client
    from app.services.reminders import batch_adjust_reminders_for_weather

    # Check for --reset flag
    reset_mode = "--reset" in sys.argv

    app = create_app()

    with app.app_context():
        # Prompt for email
        email = input("Enter your email: ").strip()

        supabase = supabase_client.get_admin_client()
        response = supabase.table("profiles").select("id, email, city").eq("email", email).execute()

        if response.data:
            # Get user ID and city
            user_id = response.data[0]['id']
            stored_city = response.data[0].get('city')

            print(f"\n✅ User ID: {user_id}")
            print(f"📍 Stored City: {stored_city or 'Not set'}")

            # Prompt for city (use stored city as default)
            city_input = input(f"\nEnter city to test (or press Enter to use '{stored_city}'): ").strip()
            city = city_input if city_input else stored_city

            if not city:
                print("❌ No city provided. Set your city at /dashboard/account")
            else:
                # Clear existing adjustments if --reset flag
                if reset_mode:
                    print(f"\n🗑️  Clearing existing weather adjustments...")
                    cleared = clear_weather_adjustments(supabase, user_id)
                    print(f"   Cleared {cleared} reminder(s)")

                print(f"\n🔄 Running weather adjustment for {city}...\n")

                # Run adjustment
                stats = batch_adjust_reminders_for_weather(user_id, city)

                print("\n" + "=" * 60)
                print("✅ Results:")
                print(f"   Reminders checked: {stats.get('total_checked', 0)}")
                print(f"   Reminders adjusted: {stats.get('adjusted', 0)}")
                print(f"   Reminders skipped: {stats.get('skipped', 0)}")
                print(f"   Errors: {stats.get('errors', 0)}")
                print("=" * 60)
        else:
            print("\n❌ User not found")


# Allow running directly
if __name__ == "__main__":
    run_manual_test()
