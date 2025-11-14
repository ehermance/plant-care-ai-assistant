"""
Analytics event tracking service.

Tracks user behavior events for product metrics:
- Activation Rate (users who add first plant)
- Weekly Active Users (WAU)
- Monthly Active Users (MAU)
- Reminder Completion Rate
- Stickiness (WAU/MAU)
- D30 Retention
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from app.services.supabase_client import get_admin_client


# Event type constants
EVENT_USER_SIGNUP = "user_signup"
EVENT_USER_FIRST_LOGIN = "user_first_login"
EVENT_PLANT_ADDED = "plant_added"
EVENT_FIRST_PLANT_ADDED = "first_plant_added"
EVENT_REMINDER_CREATED = "reminder_created"
EVENT_REMINDER_COMPLETED = "reminder_completed"
EVENT_REMINDER_SNOOZED = "reminder_snoozed"
EVENT_JOURNAL_ENTRY_CREATED = "journal_entry_created"
EVENT_AI_QUESTION_ASKED = "ai_question_asked"
EVENT_PAGE_VIEW = "page_view"


def track_event(
    user_id: str,
    event_type: str,
    event_data: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Track an analytics event.

    Args:
        user_id: UUID of the user performing the action
        event_type: Type of event (use EVENT_* constants)
        event_data: Optional JSON data associated with the event

    Returns:
        Tuple of (event_id, error_message)
    """
    if event_data is None:
        event_data = {}

    try:
        supabase = get_admin_client()

        # Call database function to track event
        result = supabase.rpc(
            "track_analytics_event",
            {
                "p_user_id": user_id,
                "p_event_type": event_type,
                "p_event_data": event_data,
            },
        ).execute()

        if result.data:
            return result.data, None
        else:
            return None, "Failed to track event"

    except Exception as e:
        print(f"Error tracking analytics event: {str(e)}")
        return None, str(e)


def get_activation_rate(
    start_date: Optional[date] = None, end_date: Optional[date] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Get activation rate (% of users who added at least one plant).

    Args:
        start_date: Start date for cohort (default: 30 days ago)
        end_date: End date for cohort (default: today)

    Returns:
        Tuple of (stats_dict, error_message)
        stats_dict contains: total_signups, activated_users, activation_rate
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()

    try:
        supabase = get_admin_client()

        result = supabase.rpc(
            "get_activation_rate",
            {
                "p_start_date": start_date.isoformat(),
                "p_end_date": end_date.isoformat(),
            },
        ).execute()

        if result.data and len(result.data) > 0:
            return result.data[0], None
        else:
            return None, "No data available"

    except Exception as e:
        print(f"Error getting activation rate: {str(e)}")
        return None, str(e)


def get_weekly_active_users(end_date: Optional[date] = None) -> Tuple[Optional[int], Optional[str]]:
    """
    Get Weekly Active Users (WAU).

    Args:
        end_date: End date for the week (default: today)

    Returns:
        Tuple of (wau_count, error_message)
    """
    if end_date is None:
        end_date = date.today()

    try:
        supabase = get_admin_client()

        result = supabase.rpc(
            "get_weekly_active_users", {"p_end_date": end_date.isoformat()}
        ).execute()

        if result.data is not None:
            return result.data, None
        else:
            return None, "No data available"

    except Exception as e:
        print(f"Error getting WAU: {str(e)}")
        return None, str(e)


def get_monthly_active_users(end_date: Optional[date] = None) -> Tuple[Optional[int], Optional[str]]:
    """
    Get Monthly Active Users (MAU).

    Args:
        end_date: End date for the month (default: today)

    Returns:
        Tuple of (mau_count, error_message)
    """
    if end_date is None:
        end_date = date.today()

    try:
        supabase = get_admin_client()

        result = supabase.rpc(
            "get_monthly_active_users", {"p_end_date": end_date.isoformat()}
        ).execute()

        if result.data is not None:
            return result.data, None
        else:
            return None, "No data available"

    except Exception as e:
        print(f"Error getting MAU: {str(e)}")
        return None, str(e)


def get_stickiness(end_date: Optional[date] = None) -> Tuple[Optional[float], Optional[str]]:
    """
    Get stickiness ratio (WAU/MAU * 100).

    Args:
        end_date: End date for calculation (default: today)

    Returns:
        Tuple of (stickiness_percentage, error_message)
    """
    if end_date is None:
        end_date = date.today()

    try:
        supabase = get_admin_client()

        result = supabase.rpc("get_stickiness", {"p_end_date": end_date.isoformat()}).execute()

        if result.data is not None:
            return result.data, None
        else:
            return None, "No data available"

    except Exception as e:
        print(f"Error getting stickiness: {str(e)}")
        return None, str(e)


def get_reminder_completion_rate(
    start_date: Optional[date] = None, end_date: Optional[date] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Get reminder completion rate.

    Args:
        start_date: Start date for period (default: 30 days ago)
        end_date: End date for period (default: today)

    Returns:
        Tuple of (stats_dict, error_message)
        stats_dict contains: total_completions, total_due, completion_rate
    """
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()

    try:
        supabase = get_admin_client()

        result = supabase.rpc(
            "get_reminder_completion_rate",
            {
                "p_start_date": start_date.isoformat(),
                "p_end_date": end_date.isoformat(),
            },
        ).execute()

        if result.data and len(result.data) > 0:
            return result.data[0], None
        else:
            return None, "No data available"

    except Exception as e:
        print(f"Error getting reminder completion rate: {str(e)}")
        return None, str(e)


def get_d30_retention(
    cohort_start_date: Optional[date] = None, cohort_end_date: Optional[date] = None
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Get D30 retention rate (% of users active 30 days after signup).

    Args:
        cohort_start_date: Start date for signup cohort (default: 60 days ago)
        cohort_end_date: End date for signup cohort (default: 30 days ago)

    Returns:
        Tuple of (stats_dict, error_message)
        stats_dict contains: cohort_size, retained_users, retention_rate
    """
    if cohort_start_date is None:
        cohort_start_date = date.today() - timedelta(days=60)
    if cohort_end_date is None:
        cohort_end_date = date.today() - timedelta(days=30)

    try:
        supabase = get_admin_client()

        result = supabase.rpc(
            "get_d30_retention",
            {
                "p_cohort_start_date": cohort_start_date.isoformat(),
                "p_cohort_end_date": cohort_end_date.isoformat(),
            },
        ).execute()

        if result.data and len(result.data) > 0:
            return result.data[0], None
        else:
            return None, "No data available"

    except Exception as e:
        print(f"Error getting D30 retention: {str(e)}")
        return None, str(e)


def get_all_metrics() -> Dict[str, Any]:
    """
    Get all key product metrics in one call.

    Returns:
        Dictionary containing all metrics with error handling
    """
    metrics = {
        "activation": None,
        "wau": None,
        "mau": None,
        "stickiness": None,
        "reminder_completion": None,
        "d30_retention": None,
        "errors": [],
    }

    # Activation rate (last 30 days)
    activation, error = get_activation_rate()
    if error:
        metrics["errors"].append(f"Activation: {error}")
    else:
        metrics["activation"] = activation

    # WAU
    wau, error = get_weekly_active_users()
    if error:
        metrics["errors"].append(f"WAU: {error}")
    else:
        metrics["wau"] = wau

    # MAU
    mau, error = get_monthly_active_users()
    if error:
        metrics["errors"].append(f"MAU: {error}")
    else:
        metrics["mau"] = mau

    # Stickiness
    stickiness, error = get_stickiness()
    if error:
        metrics["errors"].append(f"Stickiness: {error}")
    else:
        metrics["stickiness"] = stickiness

    # Reminder completion rate (last 30 days)
    completion, error = get_reminder_completion_rate()
    if error:
        metrics["errors"].append(f"Reminder completion: {error}")
    else:
        metrics["reminder_completion"] = completion

    # D30 retention
    retention, error = get_d30_retention()
    if error:
        metrics["errors"].append(f"D30 retention: {error}")
    else:
        metrics["d30_retention"] = retention

    return metrics
