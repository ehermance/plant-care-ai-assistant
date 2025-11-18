"""
Admin routes for viewing analytics and metrics.

Provides dashboard for:
- Activation Rate
- Weekly Active Users (WAU)
- Monthly Active Users (MAU)
- Stickiness (WAU/MAU)
- Reminder Completion Rate
- D30 Retention
"""

from __future__ import annotations
from flask import Blueprint, render_template
from app.utils.auth import require_admin
from app.services import analytics
from datetime import date, timedelta

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@require_admin
def index():
    """Admin dashboard showing all key metrics."""

    # Get all metrics
    metrics = analytics.get_all_metrics()

    # Calculate additional context
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    sixty_days_ago = today - timedelta(days=60)

    return render_template(
        "admin/index.html",
        metrics=metrics,
        today=today,
        period_start=thirty_days_ago,
        cohort_start=sixty_days_ago,
        cohort_end=thirty_days_ago,
    )


@admin_bp.route("/metrics")
@require_admin
def metrics():
    """Detailed metrics page with custom date ranges."""
    # Get individual metrics with defaults
    today = date.today()

    # Activation rate (last 30 days)
    activation, err1 = analytics.get_activation_rate()

    # WAU & MAU
    wau, err2 = analytics.get_weekly_active_users()
    mau, err3 = analytics.get_monthly_active_users()

    # Stickiness
    stickiness, err4 = analytics.get_stickiness()

    # Reminder completion rate (last 30 days)
    completion, err5 = analytics.get_reminder_completion_rate()

    # D30 retention (cohort from 60-30 days ago)
    retention, err6 = analytics.get_d30_retention()

    # Collect errors
    errors = []
    for err in [err1, err2, err3, err4, err5, err6]:
        if err:
            errors.append(err)

    return render_template(
        "admin/metrics.html",
        activation=activation,
        wau=wau,
        mau=mau,
        stickiness=stickiness,
        completion=completion,
        retention=retention,
        errors=errors,
        today=today,
    )
