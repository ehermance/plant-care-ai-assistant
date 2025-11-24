"""
User Context Service for AI Integration.

Provides consolidated user plant and reminder context for AI prompts.
Optimized for token efficiency (targeting 300-800 tokens depending on detail level).
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from .supabase_client import (
    get_user_plants,
    get_user_profile,
    get_plant_by_id
)
from .reminders import get_due_reminders, get_upcoming_reminders
from .journal import get_plant_actions, get_user_actions


def get_user_context(user_id: str) -> Dict[str, Any]:
    """
    Assemble concise user context for AI (targeting ~300-500 tokens).

    Includes:
    - All user plants (name, location, light) - concise format
    - Reminders: overdue, due today, next 7 days
    - Recent activities: last 7 days
    - Summary stats

    Args:
        user_id: User UUID

    Returns:
        Dict with plants, reminders, recent_activities, and stats
    """
    # Get all plants (minimal fields for context)
    plants = get_user_plants(user_id, fields="id,name,species,nickname,location,light")

    # Get reminders
    due_today = get_due_reminders(user_id)
    upcoming = get_upcoming_reminders(user_id, days=7)

    # Filter overdue from due_today (those with effective_due_date in past)
    today = datetime.now().date()
    overdue = []
    due_today_filtered = []

    for reminder in due_today:
        effective_due = reminder.get("effective_due_date")
        if effective_due:
            if isinstance(effective_due, str):
                effective_due = datetime.fromisoformat(effective_due).date()

            if effective_due < today:
                overdue.append(_format_reminder_context(reminder))
            else:
                due_today_filtered.append(_format_reminder_context(reminder))
        else:
            due_today_filtered.append(_format_reminder_context(reminder))

    # Format upcoming reminders with days until
    upcoming_formatted = []
    for reminder in upcoming[:10]:  # Limit to 10 upcoming
        formatted = _format_reminder_context(reminder)

        # Calculate days until
        effective_due = reminder.get("effective_due_date")
        if effective_due:
            if isinstance(effective_due, str):
                effective_due = datetime.fromisoformat(effective_due).date()
            days_until = (effective_due - today).days
            formatted["days_until"] = days_until

        upcoming_formatted.append(formatted)

    # Get recent activities (last 7 days)
    recent_activities = _get_recent_activities_summary(user_id, days=7)

    # Calculate stats
    stats = {
        "total_plants": len(plants),
        "active_reminders": len(due_today) + len(upcoming),
        "overdue_count": len(overdue),
        "due_today_count": len(due_today_filtered)
    }

    return {
        "plants": [_format_plant_context(p) for p in plants],
        "reminders": {
            "overdue": overdue,
            "due_today": due_today_filtered,
            "upcoming_week": upcoming_formatted
        },
        "recent_activities": recent_activities,
        "stats": stats
    }


def get_plant_context(user_id: str, plant_id: str) -> Dict[str, Any]:
    """
    Detailed context for specific plant (targeting ~500-800 tokens).

    Includes:
    - Full plant details
    - Last 14 days of activities (more history for focused query)
    - All active reminders for this plant
    - Plant-specific stats

    Args:
        user_id: User UUID
        plant_id: Plant UUID

    Returns:
        Dict with plant details, activities, reminders, and stats
    """
    # Get plant details
    plant = get_plant_by_id(plant_id, user_id)
    if not plant:
        return {
            "error": "Plant not found or access denied",
            "plant": None,
            "activities": [],
            "reminders": [],
            "stats": {}
        }

    # Get activities for this plant (last 14 days for more context)
    activities = _get_plant_activities_summary(plant_id, user_id, days=14)

    # Get reminders for this plant
    all_reminders = get_due_reminders(user_id) + get_upcoming_reminders(user_id, days=14)
    plant_reminders = [
        _format_reminder_context(r)
        for r in all_reminders
        if r.get("plant_id") == plant_id
    ]

    # Calculate plant-specific stats
    stats = _calculate_plant_stats(plant_id, user_id, activities)

    return {
        "plant": _format_plant_context(plant, detailed=True),
        "activities": activities,
        "reminders": plant_reminders,
        "stats": stats
    }


def _format_plant_context(plant: Dict[str, Any], detailed: bool = False) -> Dict[str, Any]:
    """Format plant data for context (concise or detailed)."""
    if not plant:
        return {}

    base = {
        "id": plant.get("id"),
        "name": plant.get("name"),
        "location": plant.get("location", "indoor_potted"),
    }

    # Add species/nickname if available (helps AI identify plant)
    if plant.get("species"):
        base["species"] = plant["species"]
    if plant.get("nickname"):
        base["nickname"] = plant["nickname"]

    if detailed:
        # Include more fields for plant-specific queries
        base["light"] = plant.get("light")
        base["notes"] = plant.get("notes")
        base["created_at"] = plant.get("created_at")
    else:
        # Just light level for general context
        if plant.get("light"):
            base["light"] = plant["light"]

    return base


def _format_reminder_context(reminder: Dict[str, Any]) -> Dict[str, Any]:
    """Format reminder data for context."""
    return {
        "plant_name": reminder.get("plant_name"),
        "type": reminder.get("reminder_type"),
        "title": reminder.get("title"),
        "weather_adjusted": bool(reminder.get("weather_adjustment_reason"))
    }


def _get_recent_activities_summary(user_id: str, days: int = 7) -> List[Dict[str, Any]]:
    """
    Get summary of recent activities across all plants.

    Returns concise list of recent care actions (last N days).

    Performance: Uses single query with JOIN instead of N+1 queries.
    Previous implementation: 1 + N queries (one per plant)
    New implementation: 1 query total (~95% performance improvement for 20+ plants)
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    # Single optimized query to get all user's activities with plant names
    # This replaces the N+1 pattern of querying each plant individually
    all_activities_raw = get_user_actions(user_id, limit=100)

    # Filter to time window and format
    all_activities = []
    for activity in all_activities_raw:
        action_at = activity.get("action_at")
        if action_at:
            # Parse timestamp
            if isinstance(action_at, str):
                action_at = datetime.fromisoformat(action_at.replace('Z', '+00:00'))

            # Only include if within time window
            if action_at >= cutoff_date:
                days_ago = (datetime.now(action_at.tzinfo) - action_at).days
                all_activities.append({
                    "plant_name": activity.get("plant_name", "Unknown"),
                    "action_type": activity.get("action_type"),
                    "days_ago": days_ago,
                    "notes": activity.get("notes")
                })

    # Sort by most recent and limit to 10
    all_activities.sort(key=lambda x: x["days_ago"])
    return all_activities[:10]


def _get_plant_activities_summary(plant_id: str, user_id: str, days: int = 14) -> List[Dict[str, Any]]:
    """
    Get summary of activities for specific plant.

    Returns detailed list of recent care actions for this plant.
    """
    cutoff_date = datetime.now() - timedelta(days=days)

    activities = get_plant_actions(plant_id, user_id, limit=50)

    recent = []
    for activity in activities:
        action_at = activity.get("action_at")
        if action_at:
            # Parse timestamp
            if isinstance(action_at, str):
                action_at = datetime.fromisoformat(action_at.replace('Z', '+00:00'))

            # Only include if within time window
            if action_at >= cutoff_date:
                days_ago = (datetime.now(action_at.tzinfo) - action_at).days
                recent.append({
                    "action_type": activity.get("action_type"),
                    "days_ago": days_ago,
                    "amount_ml": activity.get("amount_ml"),
                    "notes": activity.get("notes")
                })

    # Sort by most recent
    recent.sort(key=lambda x: x["days_ago"])
    return recent


def _calculate_plant_stats(plant_id: str, user_id: str, activities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate statistics for specific plant."""
    # Count by action type
    action_counts = {}
    for activity in activities:
        action_type = activity.get("action_type")
        action_counts[action_type] = action_counts.get(action_type, 0) + 1

    # Find last watered
    last_watered_days = None
    for activity in activities:
        if activity.get("action_type") == "water":
            last_watered_days = activity.get("days_ago")
            break

    return {
        "total_activities": len(activities),
        "last_watered_days_ago": last_watered_days,
        "action_counts": action_counts
    }
