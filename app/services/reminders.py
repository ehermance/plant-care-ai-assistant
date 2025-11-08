"""
Reminder service for plant care scheduling.

Handles creating, reading, updating, and deleting care reminders with
weather-based adjustments for outdoor plants.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List, Tuple
from datetime import date, datetime, timedelta
from app.services.supabase_client import get_client, get_admin_client
from app.services.weather import get_weather_for_city

# Frequency mappings to days
FREQUENCY_DAYS = {
    'daily': 1,
    'every_2_days': 2,
    'every_3_days': 3,
    'weekly': 7,
    'biweekly': 14,
    'monthly': 30,
    'one_time': 0,  # One-time reminders default to today
}

# Reminder type display names
REMINDER_TYPE_NAMES = {
    'watering': 'Watering',
    'fertilizing': 'Fertilizing',
    'misting': 'Misting',
    'pruning': 'Pruning',
    'repotting': 'Repotting',
    'inspection': 'Inspection',
    'custom': 'Custom Care',
}


def create_reminder(
    user_id: str,
    plant_id: str,
    reminder_type: str,
    title: str,
    frequency: str,
    custom_interval_days: Optional[int] = None,
    notes: Optional[str] = None,
    skip_weather_adjustment: bool = False,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Create a new care reminder for a plant.

    Args:
        user_id: User's UUID
        plant_id: Plant's UUID
        reminder_type: Type of reminder (watering, fertilizing, etc.)
        title: Reminder title
        frequency: How often to remind (daily, weekly, etc.)
        custom_interval_days: Days between reminders if frequency='custom'
        notes: Optional notes
        skip_weather_adjustment: If True, don't adjust for weather

    Returns:
        (reminder_dict, error_message)
    """
    supabase = get_admin_client()
    if not supabase:
        return None, "Database not configured"

    # Validate frequency
    if frequency not in FREQUENCY_DAYS and frequency != 'custom':
        return None, f"Invalid frequency: {frequency}"

    if frequency == 'custom' and not custom_interval_days:
        return None, "custom_interval_days required for custom frequency"

    # Determine if this is a recurring reminder
    is_recurring = frequency != 'one_time'

    # Calculate initial next_due date
    if frequency == 'custom':
        interval_days = custom_interval_days
    elif frequency == 'one_time':
        interval_days = 0  # Due today
    else:
        interval_days = FREQUENCY_DAYS[frequency]

    next_due = date.today() + timedelta(days=interval_days)

    try:
        # Insert reminder
        response = supabase.table("reminders").insert({
            "user_id": user_id,
            "plant_id": plant_id,
            "reminder_type": reminder_type,
            "title": title,
            "frequency": frequency,
            "custom_interval_days": custom_interval_days,
            "next_due": next_due.isoformat(),
            "notes": notes,
            "skip_weather_adjustment": skip_weather_adjustment,
            "is_active": True,
            "is_recurring": is_recurring,
        }).execute()

        if response.data:
            return response.data[0], None
        return None, "Failed to create reminder"

    except Exception as e:
        return None, f"Error creating reminder: {str(e)}"


def get_user_reminders(
    user_id: str,
    plant_id: Optional[str] = None,
    active_only: bool = True,
) -> List[Dict[str, Any]]:
    """
    Get all reminders for a user, optionally filtered by plant.

    Args:
        user_id: User's UUID
        plant_id: Optional plant UUID to filter by
        active_only: If True, only return active reminders

    Returns:
        List of reminder dictionaries
    """
    supabase = get_admin_client()
    if not supabase:
        return []

    try:
        query = supabase.table("reminders").select(
            "*, plants(id, name, nickname, photo_url, location)"
        ).eq("user_id", user_id)

        if plant_id:
            query = query.eq("plant_id", plant_id)

        if active_only:
            query = query.eq("is_active", True)

        response = query.order("next_due", desc=False).execute()

        return response.data if response.data else []

    except Exception as e:
        print(f"Error fetching reminders: {e}")
        return []


def get_due_reminders(user_id: str) -> List[Dict[str, Any]]:
    """
    Get reminders that are due today or overdue.

    Args:
        user_id: User's UUID

    Returns:
        List of due reminder dictionaries with plant info
    """
    supabase = get_admin_client()
    if not supabase:
        return []

    try:
        # Use the reminders_due_today view for optimized query
        response = supabase.table("reminders_due_today").select("*").eq("user_id", user_id).execute()

        return response.data if response.data else []

    except Exception as e:
        print(f"Error fetching due reminders: {e}")
        return []


def get_upcoming_reminders(user_id: str, days: int = 7) -> List[Dict[str, Any]]:
    """
    Get reminders due in the next N days (excluding today).

    Args:
        user_id: User's UUID
        days: Number of days to look ahead (default 7)

    Returns:
        List of upcoming reminder dictionaries with plant info
    """
    supabase = get_admin_client()
    if not supabase:
        return []

    try:
        # Use the reminders_upcoming view
        response = supabase.table("reminders_upcoming").select("*").eq("user_id", user_id).execute()

        return response.data if response.data else []

    except Exception as e:
        print(f"Error fetching upcoming reminders: {e}")
        return []


def get_reminder_by_id(reminder_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single reminder by ID (with ownership check).

    Args:
        reminder_id: Reminder's UUID
        user_id: User's UUID (for authorization)

    Returns:
        Reminder dictionary or None
    """
    supabase = get_admin_client()
    if not supabase:
        return None

    try:
        response = supabase.table("reminders").select(
            "*, plants(id, name, nickname, photo_url, location)"
        ).eq("id", reminder_id).eq("user_id", user_id).single().execute()

        return response.data if response.data else None

    except Exception as e:
        print(f"Error fetching reminder: {e}")
        return None


def mark_reminder_complete(reminder_id: str, user_id: str) -> Tuple[bool, Optional[str]]:
    """
    Mark a reminder as complete and calculate next due date.

    Uses the database function for atomic operation.

    Args:
        reminder_id: Reminder's UUID
        user_id: User's UUID (for authorization)

    Returns:
        (success, error_message)
    """
    supabase = get_admin_client()
    if not supabase:
        return False, "Database not configured"

    try:
        # Call database function with user_id
        response = supabase.rpc("complete_reminder", {
            "p_reminder_id": reminder_id,
            "p_user_id": user_id
        }).execute()

        if response.data and len(response.data) > 0:
            result = response.data[0]
            if result.get("success"):
                return True, None
            return False, result.get("message", "Failed to complete reminder")

        return False, "Unexpected response from database"

    except Exception as e:
        return False, f"Error completing reminder: {str(e)}"


def snooze_reminder(
    reminder_id: str,
    user_id: str,
    days: int = 1
) -> Tuple[bool, Optional[str]]:
    """
    Snooze a reminder by N days.

    Args:
        reminder_id: Reminder's UUID
        user_id: User's UUID (for authorization)
        days: Number of days to snooze (1-30)

    Returns:
        (success, error_message)
    """
    supabase = get_admin_client()
    if not supabase:
        return False, "Database not configured"

    if days < 1 or days > 30:
        return False, "Snooze days must be between 1 and 30"

    try:
        # Call database function with user_id
        response = supabase.rpc("snooze_reminder", {
            "p_reminder_id": reminder_id,
            "p_user_id": user_id,
            "p_days": days
        }).execute()

        if response.data and len(response.data) > 0:
            result = response.data[0]
            if result.get("success"):
                return True, None
            return False, result.get("message", "Failed to snooze reminder")

        return False, "Unexpected response from database"

    except Exception as e:
        return False, f"Error snoozing reminder: {str(e)}"


def update_reminder(
    reminder_id: str,
    user_id: str,
    **kwargs
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Update a reminder's fields.

    Args:
        reminder_id: Reminder's UUID
        user_id: User's UUID (for authorization)
        **kwargs: Fields to update (title, notes, frequency, etc.)

    Returns:
        (updated_reminder, error_message)
    """
    supabase = get_admin_client()
    if not supabase:
        return None, "Database not configured"

    # Remove fields that shouldn't be updated this way
    disallowed_fields = ['id', 'user_id', 'plant_id', 'created_at', 'last_completed_at']
    update_data = {k: v for k, v in kwargs.items() if k not in disallowed_fields}

    if not update_data:
        return None, "No fields to update"

    try:
        response = supabase.table("reminders").update(update_data).eq(
            "id", reminder_id
        ).eq("user_id", user_id).execute()

        if response.data:
            return response.data[0], None
        return None, "Failed to update reminder"

    except Exception as e:
        return None, f"Error updating reminder: {str(e)}"


def delete_reminder(reminder_id: str, user_id: str) -> Tuple[bool, Optional[str]]:
    """
    Delete a reminder (soft delete by setting is_active=False).

    Args:
        reminder_id: Reminder's UUID
        user_id: User's UUID (for authorization)

    Returns:
        (success, error_message)
    """
    supabase = get_admin_client()
    if not supabase:
        return False, "Database not configured"

    try:
        # Soft delete
        response = supabase.table("reminders").update({
            "is_active": False
        }).eq("id", reminder_id).eq("user_id", user_id).execute()

        if response.data:
            return True, None
        return False, "Reminder not found or unauthorized"

    except Exception as e:
        return False, f"Error deleting reminder: {str(e)}"


def toggle_reminder_status(reminder_id: str, user_id: str) -> Tuple[bool, Optional[str]]:
    """
    Toggle a reminder's active status (activate/deactivate).

    When reactivating, sets next_due to tomorrow.

    Args:
        reminder_id: Reminder's UUID
        user_id: User's UUID (for authorization)

    Returns:
        (success, error_message)
    """
    from datetime import datetime, timedelta

    supabase = get_admin_client()
    if not supabase:
        return False, "Database not configured"

    try:
        # Get current reminder to check is_active status
        response = supabase.table("reminders").select("is_active, frequency").eq("id", reminder_id).eq("user_id", user_id).execute()

        if not response.data:
            return False, "Reminder not found or unauthorized"

        current_reminder = response.data[0]
        current_status = current_reminder.get("is_active", True)
        new_status = not current_status

        # Prepare update data
        update_data = {"is_active": new_status}

        # If reactivating (False -> True), set next_due to tomorrow
        if new_status:
            tomorrow = (datetime.now() + timedelta(days=1)).date()
            update_data["next_due"] = tomorrow.isoformat()

        # Update reminder
        response = supabase.table("reminders").update(update_data).eq("id", reminder_id).eq("user_id", user_id).execute()

        if response.data:
            return True, None
        return False, "Failed to toggle reminder status"

    except Exception as e:
        return False, f"Error toggling reminder status: {str(e)}"


def get_reminder_stats(user_id: str) -> Dict[str, int]:
    """
    Get reminder statistics for a user.

    Args:
        user_id: User's UUID

    Returns:
        Dictionary with stats (total, due_today, upcoming, etc.)
    """
    supabase = get_admin_client()
    if not supabase:
        return {
            "total_reminders": 0,
            "active_reminders": 0,
            "due_today": 0,
            "upcoming_7_days": 0,
            "completed_this_week": 0,
        }

    try:
        response = supabase.rpc("get_reminder_stats", {
            "p_user_id": user_id
        }).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]

        return {
            "total_reminders": 0,
            "active_reminders": 0,
            "due_today": 0,
            "upcoming_7_days": 0,
            "completed_this_week": 0,
        }

    except Exception as e:
        print(f"Error fetching reminder stats: {e}")
        return {
            "total_reminders": 0,
            "active_reminders": 0,
            "due_today": 0,
            "upcoming_7_days": 0,
            "completed_this_week": 0,
        }


def adjust_reminder_for_weather(
    reminder_id: str,
    user_id: str,
    city: str,
    plant_location: str = "outdoor_potted"
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Adjust a reminder's due date based on weather forecast.

    Logic:
    - If rain expected in next 3 days: Delay watering by 2-3 days
    - If hot/dry (>32°C): Advance watering by 1 day
    - Only applies to outdoor plants and watering reminders

    Args:
        reminder_id: Reminder's UUID
        user_id: User's UUID
        city: City name for weather lookup
        plant_location: Plant location context (outdoor_potted, outdoor_bed, indoor_potted)

    Returns:
        (adjusted, message, weather_data)
    """
    # Only adjust outdoor plants
    if "indoor" in plant_location.lower():
        return False, "Weather adjustments only apply to outdoor plants", None

    # Get reminder
    reminder = get_reminder_by_id(reminder_id, user_id)
    if not reminder:
        return False, "Reminder not found", None

    # Only adjust watering reminders
    if reminder.get("reminder_type") != "watering":
        return False, "Weather adjustments only apply to watering reminders", None

    # Check if weather adjustment is disabled for this reminder
    if reminder.get("skip_weather_adjustment"):
        return False, "Weather adjustment disabled for this reminder", None

    # Get weather forecast
    weather = get_weather_for_city(city)
    if not weather:
        return False, "Could not fetch weather data", None

    try:
        supabase = get_admin_client()
        if not supabase:
            return False, "Database not configured", None

        current_temp = weather.get("temp_c")
        conditions = weather.get("conditions", "").lower()

        adjustment_made = False
        adjustment_reason = None
        new_due_date = None

        # Hot/dry conditions - advance watering
        if current_temp and current_temp >= 32:
            original_due = date.fromisoformat(reminder["next_due"])
            new_due_date = original_due - timedelta(days=1)

            # Don't advance to past
            if new_due_date < date.today():
                new_due_date = date.today()

            adjustment_reason = f"Advanced due to hot weather ({current_temp}°C)"
            adjustment_made = True

        # Rain conditions - delay watering
        elif any(keyword in conditions for keyword in ['rain', 'drizzle', 'shower', 'thunderstorm']):
            original_due = date.fromisoformat(reminder["next_due"])
            new_due_date = original_due + timedelta(days=2)

            adjustment_reason = f"Delayed due to rain forecast ({conditions})"
            adjustment_made = True

        if adjustment_made and new_due_date:
            # Update reminder with weather adjustment
            supabase.table("reminders").update({
                "weather_adjusted_due": new_due_date.isoformat(),
                "weather_adjustment_reason": adjustment_reason,
            }).eq("id", reminder_id).eq("user_id", user_id).execute()

            return True, adjustment_reason, weather

        return False, "No weather adjustment needed", weather

    except Exception as e:
        return False, f"Error adjusting for weather: {str(e)}", None


def clear_weather_adjustment(reminder_id: str, user_id: str) -> Tuple[bool, Optional[str]]:
    """
    Clear weather adjustment and revert to original schedule.

    Args:
        reminder_id: Reminder's UUID
        user_id: User's UUID

    Returns:
        (success, error_message)
    """
    supabase = get_admin_client()
    if not supabase:
        return False, "Database not configured"

    try:
        response = supabase.table("reminders").update({
            "weather_adjusted_due": None,
            "weather_adjustment_reason": None,
        }).eq("id", reminder_id).eq("user_id", user_id).execute()

        if response.data:
            return True, None
        return False, "Reminder not found"

    except Exception as e:
        return False, f"Error clearing weather adjustment: {str(e)}"


def batch_adjust_reminders_for_weather(
    user_id: str,
    city: str
) -> Dict[str, int]:
    """
    Adjust all watering reminders for a user based on current weather.

    Useful for daily cron job or user-triggered refresh.

    Args:
        user_id: User's UUID
        city: City name for weather lookup

    Returns:
        Dictionary with counts (total_checked, adjusted, skipped)
    """
    reminders = get_user_reminders(user_id, active_only=True)

    stats = {
        "total_checked": 0,
        "adjusted": 0,
        "skipped": 0,
        "errors": 0,
    }

    for reminder in reminders:
        stats["total_checked"] += 1

        if reminder.get("reminder_type") != "watering":
            stats["skipped"] += 1
            continue

        if reminder.get("skip_weather_adjustment"):
            stats["skipped"] += 1
            continue

        # Get plant location from joined data
        plant = reminder.get("plants", {})
        plant_location = plant.get("location", "indoor_potted")

        success, _, _ = adjust_reminder_for_weather(
            reminder["id"],
            user_id,
            city,
            plant_location
        )

        if success:
            stats["adjusted"] += 1
        else:
            stats["skipped"] += 1

    return stats


def get_reminders_for_month(user_id: str, year: int, month: int) -> List[Dict[str, Any]]:
    """
    Get all active reminders with next_due dates in the specified month.

    Args:
        user_id: User's UUID
        year: Year (e.g., 2025)
        month: Month (1-12)

    Returns:
        List of reminder dictionaries with plant info, grouped by date
    """
    supabase = get_admin_client()
    if not supabase:
        return []

    try:
        # Calculate first and last day of month
        from calendar import monthrange
        first_day = date(year, month, 1)
        last_day_num = monthrange(year, month)[1]
        last_day = date(year, month, last_day_num)

        # Get all active reminders with next_due in this month
        response = supabase.table("reminders") \
            .select("*, plants(id, name, nickname, photo_url, location)") \
            .eq("user_id", user_id) \
            .eq("is_active", True) \
            .gte("next_due", first_day.isoformat()) \
            .lte("next_due", last_day.isoformat()) \
            .order("next_due") \
            .execute()

        return response.data if response.data else []

    except Exception as e:
        print(f"Error fetching reminders for month: {e}")
        return []
