"""
Unit tests for reminder adjustment engine (app/services/reminder_adjustments.py).

Tests weather-aware reminder adjustments, priority-based conflict resolution,
and automatic vs suggestive adjustment logic.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta
from app.services import reminder_adjustments


class TestEvaluateReminderAdjustment:
    """Test reminder adjustment evaluation logic."""

    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_freeze_warning_automatic_postpone(
        self, mock_light, mock_chars, mock_seasonal, mock_temp, mock_precip, mock_weather
    ):
        """Freeze warnings should trigger automatic postponement (highest priority)."""
        # Setup mocks
        mock_weather.return_value = {"temp_f": 35, "humidity": 70}
        mock_precip.return_value = 0.0
        mock_temp.return_value = {
            "temp_min_f": 28,
            "temp_max_f": 40,
            "freeze_risk": True
        }
        mock_seasonal.return_value = {"season": "winter", "is_dormancy_period": False}
        mock_chars.return_value = {"cold_tolerance": "tender", "water_needs": "moderate"}
        mock_light.return_value = 1.0

        reminder = {
            "id": "r1",
            "reminder_type": "watering",
            "next_due": (date.today() + timedelta(days=1)).isoformat(),
            "skip_weather_adjustment": False
        }

        plant = {
            "id": "p1",
            "location": "outdoor_potted",
            "species": "Tomato"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Seattle, WA"
        )

        assert result["action"] == reminder_adjustments.ACTION_POSTPONE
        assert result["mode"] == reminder_adjustments.MODE_AUTOMATIC
        assert result["days"] == 2
        assert result["priority"] == reminder_adjustments.PRIORITY_SAFETY
        assert "freeze" in result["reason"].lower()

    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_heavy_rain_automatic_postpone(
        self, mock_light, mock_chars, mock_seasonal, mock_temp, mock_precip, mock_weather
    ):
        """Heavy rain should trigger automatic postponement for outdoor plants."""
        mock_weather.return_value = {"temp_f": 65, "humidity": 85}
        mock_precip.return_value = 0.8  # Heavy rain (>0.5")
        mock_temp.return_value = {
            "temp_min_f": 60,
            "temp_max_f": 70,
            "freeze_risk": False
        }
        mock_seasonal.return_value = {"season": "spring", "is_dormancy_period": False}
        mock_chars.return_value = {"water_needs": "moderate"}
        mock_light.return_value = 1.0

        reminder = {
            "reminder_type": "watering",
            "next_due": (date.today() + timedelta(days=1)).isoformat(),
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "outdoor_bed",
            "species": "Rose"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Seattle, WA"
        )

        assert result["action"] == reminder_adjustments.ACTION_POSTPONE
        assert result["mode"] == reminder_adjustments.MODE_AUTOMATIC
        assert result["days"] == 2
        assert result["priority"] == reminder_adjustments.PRIORITY_PRECIPITATION
        assert "heavy rain" in result["reason"].lower()
        assert result["details"]["precipitation_inches"] == 0.8

    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_overdue_reminder_still_adjusted_for_rain(
        self, mock_light, mock_chars, mock_seasonal, mock_temp, mock_precip, mock_weather
    ):
        """Overdue reminders should still be adjusted when it's raining (Option B behavior)."""
        mock_weather.return_value = {"temp_f": 65, "humidity": 85}
        mock_precip.return_value = 0.8  # Heavy rain
        mock_temp.return_value = {
            "temp_min_f": 60,
            "temp_max_f": 70,
            "freeze_risk": False
        }
        mock_seasonal.return_value = {"season": "spring", "is_dormancy_period": False}
        mock_chars.return_value = {"water_needs": "moderate"}
        mock_light.return_value = 1.0

        # Reminder that is 2 days OVERDUE
        reminder = {
            "reminder_type": "watering",
            "next_due": (date.today() - timedelta(days=2)).isoformat(),
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "outdoor_potted",
            "species": "Tomato"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Seattle, WA"
        )

        # Should be postponed due to rain, NOT skipped because it's overdue
        assert result["action"] == reminder_adjustments.ACTION_POSTPONE
        assert result["mode"] == reminder_adjustments.MODE_AUTOMATIC
        assert "rain" in result["reason"].lower()

    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_today_reminder_adjusted_for_rain(
        self, mock_light, mock_chars, mock_seasonal, mock_temp, mock_precip, mock_weather
    ):
        """Reminders due today should be adjusted when it's raining."""
        mock_weather.return_value = {"temp_f": 65, "humidity": 85}
        mock_precip.return_value = 0.8  # Heavy rain
        mock_temp.return_value = {
            "temp_min_f": 60,
            "temp_max_f": 70,
            "freeze_risk": False
        }
        mock_seasonal.return_value = {"season": "spring", "is_dormancy_period": False}
        mock_chars.return_value = {"water_needs": "moderate"}
        mock_light.return_value = 1.0

        # Reminder due TODAY
        reminder = {
            "reminder_type": "watering",
            "next_due": date.today().isoformat(),
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "outdoor_bed",
            "species": "Rose"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Seattle, WA"
        )

        # Should be postponed due to rain
        assert result["action"] == reminder_adjustments.ACTION_POSTPONE
        assert "rain" in result["reason"].lower()

    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_already_adjusted_reminder_readjusts_when_adjusted_date_is_today(
        self, mock_light, mock_chars, mock_seasonal, mock_temp, mock_precip, mock_weather
    ):
        """Reminders with weather_adjusted_due of TODAY should be re-evaluated."""
        mock_weather.return_value = {"temp_f": 65, "humidity": 85}
        mock_precip.return_value = 0.8  # Heavy rain still happening
        mock_temp.return_value = {
            "temp_min_f": 60,
            "temp_max_f": 70,
            "freeze_risk": False
        }
        mock_seasonal.return_value = {"season": "spring", "is_dormancy_period": False}
        mock_chars.return_value = {"water_needs": "moderate"}
        mock_light.return_value = 1.0

        # Reminder was previously adjusted to TODAY - should re-evaluate
        reminder = {
            "reminder_type": "watering",
            "next_due": (date.today() - timedelta(days=1)).isoformat(),  # Originally due yesterday
            "weather_adjusted_due": date.today().isoformat(),  # Was postponed to today
            "weather_adjustment_reason": "Previous adjustment",
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "outdoor_potted",
            "species": "Tomato"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Seattle, WA"
        )

        # Should re-evaluate and postpone again since rain is still happening
        assert result["action"] == reminder_adjustments.ACTION_POSTPONE
        assert "rain" in result["reason"].lower()

    @patch('app.services.reminder_adjustments.get_weather_for_city')
    def test_already_adjusted_reminder_skips_when_adjusted_date_is_future(
        self, mock_weather
    ):
        """Reminders with weather_adjusted_due in FUTURE should NOT be re-evaluated."""
        mock_weather.return_value = {"temp_f": 65, "humidity": 85}

        # Reminder was previously adjusted to TOMORROW - should skip
        reminder = {
            "reminder_type": "watering",
            "next_due": date.today().isoformat(),
            "weather_adjusted_due": (date.today() + timedelta(days=1)).isoformat(),  # Adjusted to tomorrow
            "weather_adjustment_reason": "Previous adjustment",
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "outdoor_potted",
            "species": "Tomato"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Seattle, WA"
        )

        # Should skip - already adjusted and not due yet
        assert result["action"] == reminder_adjustments.ACTION_NONE

    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_light_rain_suggestion(
        self, mock_light, mock_chars, mock_seasonal, mock_temp, mock_precip, mock_weather
    ):
        """Light rain should create suggestion, not automatic adjustment."""
        mock_weather.return_value = {"temp_f": 65, "humidity": 70}
        mock_precip.return_value = 0.3  # Light rain (0.25" - 0.5")
        mock_temp.return_value = {
            "temp_min_f": 55,
            "temp_max_f": 70,
            "freeze_risk": False
        }
        mock_seasonal.return_value = {"season": "spring", "is_dormancy_period": False}
        mock_chars.return_value = {"water_needs": "moderate"}
        mock_light.return_value = 1.0

        reminder = {
            "reminder_type": "watering",
            "next_due": (date.today() + timedelta(days=1)).isoformat(),
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "outdoor_potted",
            "species": "Lavender"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Portland, OR"
        )

        assert result["action"] == reminder_adjustments.ACTION_POSTPONE
        assert result["mode"] == reminder_adjustments.MODE_SUGGESTION  # Not automatic
        assert result["days"] == 1
        assert "light rain" in result["reason"].lower()

    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_indoor_plant_no_rain_adjustment(
        self, mock_light, mock_chars, mock_seasonal, mock_temp, mock_precip, mock_weather
    ):
        """Indoor plants should not be affected by rain."""
        mock_weather.return_value = {"temp_f": 70, "humidity": 50}
        mock_precip.return_value = 1.5  # Heavy rain
        mock_temp.return_value = {
            "temp_min_f": 65,
            "temp_max_f": 75,
            "freeze_risk": False
        }
        mock_seasonal.return_value = {"season": "summer", "is_dormancy_period": False}
        mock_chars.return_value = {"water_needs": "moderate"}
        mock_light.return_value = 1.0

        reminder = {
            "reminder_type": "watering",
            "next_due": (date.today() + timedelta(days=1)).isoformat(),
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "indoor_potted",  # Indoor
            "species": "Monstera"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Seattle, WA"
        )

        # Should not adjust for rain (indoor)
        # May have other adjustments (light, etc.) but not rain
        if result["action"] != reminder_adjustments.ACTION_NONE:
            assert "rain" not in result["reason"].lower()

    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_extreme_heat_tender_plant_suggestion(
        self, mock_light, mock_chars, mock_seasonal, mock_temp, mock_precip, mock_weather
    ):
        """Extreme heat with tender plants should suggest advancing watering."""
        mock_weather.return_value = {"temp_f": 98, "humidity": 30}
        mock_precip.return_value = 0.0
        mock_temp.return_value = {
            "temp_min_f": 85,
            "temp_max_f": 98,
            "freeze_risk": False
        }
        mock_seasonal.return_value = {"season": "summer", "is_dormancy_period": False}
        mock_chars.return_value = {"cold_tolerance": "tender", "water_needs": "moderate"}
        mock_light.return_value = 1.0

        reminder = {
            "reminder_type": "watering",
            "next_due": (date.today() + timedelta(days=2)).isoformat(),
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "outdoor_potted",
            "species": "Impatiens"  # Tender plant
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Phoenix, AZ"
        )

        assert result["action"] == reminder_adjustments.ACTION_ADVANCE
        assert result["mode"] == reminder_adjustments.MODE_SUGGESTION
        assert result["days"] == -1  # Negative = advance
        assert result["priority"] == reminder_adjustments.PRIORITY_SAFETY
        assert "extreme heat" in result["reason"].lower()

    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_dormancy_period_postpone_suggestion(
        self, mock_light, mock_chars, mock_seasonal, mock_temp, mock_precip, mock_weather
    ):
        """Perennial plants in dormancy should get postponement suggestion."""
        mock_weather.return_value = {"temp_f": 40, "humidity": 60}
        mock_precip.return_value = 0.0
        mock_temp.return_value = {
            "temp_min_f": 35,
            "temp_max_f": 45,
            "freeze_risk": False
        }
        mock_seasonal.return_value = {
            "season": "winter",
            "is_dormancy_period": True
        }
        mock_chars.return_value = {
            "lifecycle": "perennial",
            "water_needs": "moderate"
        }
        mock_light.return_value = 1.0

        reminder = {
            "reminder_type": "watering",
            "next_due": (date.today() + timedelta(days=1)).isoformat(),
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "outdoor_bed",
            "species": "Lavender"  # Perennial
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Boston, MA"
        )

        assert result["action"] == reminder_adjustments.ACTION_POSTPONE
        assert result["mode"] == reminder_adjustments.MODE_SUGGESTION
        assert result["priority"] == reminder_adjustments.PRIORITY_SEASONAL
        assert "dormancy" in result["reason"].lower()

    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_priority_conflict_resolution(
        self, mock_light, mock_chars, mock_seasonal, mock_temp, mock_precip, mock_weather
    ):
        """When multiple adjustments possible, highest priority should win."""
        # Setup scenario with both freeze warning (priority 1) and light rain (priority 2)
        mock_weather.return_value = {"temp_f": 35, "humidity": 85}
        mock_precip.return_value = 0.3  # Light rain
        mock_temp.return_value = {
            "temp_min_f": 28,  # Freeze warning!
            "temp_max_f": 40,
            "freeze_risk": True
        }
        mock_seasonal.return_value = {"season": "winter", "is_dormancy_period": False}
        mock_chars.return_value = {"water_needs": "moderate"}
        mock_light.return_value = 1.0

        reminder = {
            "reminder_type": "watering",
            "next_due": (date.today() + timedelta(days=1)).isoformat(),
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "outdoor_potted",
            "species": "Test Plant"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Minneapolis, MN"
        )

        # Freeze warning (priority 1) should win over rain (priority 2)
        assert result["priority"] == reminder_adjustments.PRIORITY_SAFETY
        assert "freeze" in result["reason"].lower()

    def test_skip_weather_adjustment_flag(self):
        """Reminders with skip_weather_adjustment=True should not be adjusted."""
        reminder = {
            "reminder_type": "watering",
            "next_due": (date.today() + timedelta(days=1)).isoformat(),
            "skip_weather_adjustment": True  # User opted out
        }

        plant = {
            "location": "outdoor_bed",
            "species": "Test"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Seattle, WA"
        )

        assert result["action"] == reminder_adjustments.ACTION_NONE

    def test_non_watering_reminder_not_adjusted(self):
        """Only watering and misting reminders should be adjusted."""
        reminder = {
            "reminder_type": "fertilizing",  # Not watering
            "next_due": (date.today() + timedelta(days=1)).isoformat(),
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "outdoor_bed",
            "species": "Test"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, "Seattle, WA"
        )

        assert result["action"] == reminder_adjustments.ACTION_NONE

    def test_no_city_no_adjustment(self):
        """Without city/weather data, no adjustment should be made."""
        reminder = {
            "reminder_type": "watering",
            "next_due": (date.today() + timedelta(days=1)).isoformat(),
            "skip_weather_adjustment": False
        }

        plant = {
            "location": "outdoor_bed",
            "species": "Test"
        }

        result = reminder_adjustments.evaluate_reminder_adjustment(
            reminder, plant, None  # No city
        )

        assert result["action"] == reminder_adjustments.ACTION_NONE


class TestApplyAutomaticAdjustments:
    """Test automatic adjustment application."""

    @patch('app.services.supabase_client.get_admin_client')
    @patch('app.services.reminder_adjustments.evaluate_reminder_adjustment')
    def test_applies_automatic_adjustments(self, mock_evaluate, mock_db):
        """Reminders automatically postponed to future dates should be excluded from results."""
        # Setup mock to return automatic postpone adjustment
        mock_evaluate.return_value = {
            "action": reminder_adjustments.ACTION_POSTPONE,
            "mode": reminder_adjustments.MODE_AUTOMATIC,
            "days": 2,
            "reason": "Heavy rain expected",
            "details": {"precipitation_inches": 0.8}
        }
        mock_db.return_value = None  # DB operations optional

        # Reminder due today - when postponed by 2 days, it's in the future
        reminders = [{
            "id": "r1",
            "user_id": "u1",
            "plant_id": "p1",
            "reminder_type": "watering",
            "next_due": date.today().isoformat()
        }]

        plants = {
            "p1": {"location": "outdoor_bed", "species": "Tomato"}
        }

        result = reminder_adjustments.apply_automatic_adjustments(
            reminders, plants, "Seattle, WA"
        )

        # Reminder should be EXCLUDED because it's been postponed to a future date
        assert len(result) == 0

    @patch('app.services.supabase_client.get_admin_client')
    @patch('app.services.reminder_adjustments.evaluate_reminder_adjustment')
    def test_advance_adjustment_keeps_reminder_if_due_today(self, mock_evaluate, mock_db):
        """Reminders advanced to today should be included in results."""
        # Setup mock to return automatic advance adjustment
        mock_evaluate.return_value = {
            "action": reminder_adjustments.ACTION_ADVANCE,
            "mode": reminder_adjustments.MODE_AUTOMATIC,
            "days": -1,
            "reason": "Hot weather - water earlier",
            "details": {}
        }
        mock_db.return_value = None

        # Reminder due tomorrow - when advanced by 1 day, it's due today
        tomorrow = date.today() + timedelta(days=1)
        reminders = [{
            "id": "r1",
            "user_id": "u1",
            "plant_id": "p1",
            "reminder_type": "watering",
            "next_due": tomorrow.isoformat()
        }]

        plants = {
            "p1": {"location": "outdoor_bed", "species": "Tomato"}
        }

        result = reminder_adjustments.apply_automatic_adjustments(
            reminders, plants, "Seattle, WA"
        )

        # Reminder should be INCLUDED because it's now due today
        assert len(result) == 1
        assert "adjustment" in result[0]
        assert result[0]["adjustment"]["action"] == reminder_adjustments.ACTION_ADVANCE
        assert result[0]["adjustment"]["adjusted_due_date"] == date.today().isoformat()

    @patch('app.services.reminder_adjustments.evaluate_reminder_adjustment')
    def test_skips_suggestion_mode_adjustments(self, mock_evaluate):
        """Suggestion-mode adjustments should not be auto-applied."""
        mock_evaluate.return_value = {
            "action": reminder_adjustments.ACTION_POSTPONE,
            "mode": reminder_adjustments.MODE_SUGGESTION,  # Suggestion, not automatic
            "days": 1,
            "reason": "Light rain expected"
        }

        reminders = [{
            "id": "r1",
            "plant_id": "p1",
            "next_due": "2025-12-03"
        }]

        plants = {
            "p1": {"location": "outdoor_bed", "species": "Test"}
        }

        result = reminder_adjustments.apply_automatic_adjustments(
            reminders, plants, "Seattle, WA"
        )

        # Should not have adjustment (suggestions don't auto-apply)
        assert "adjustment" not in result[0]


class TestCreateSuggestionNotification:
    """Test suggestion notification creation."""

    def test_creates_postpone_notification(self):
        """Should create friendly notification for postpone action."""
        reminder = {
            "id": "r1",
            "plant_name": "Tomato Plant",
            "reminder_type": "watering"
        }

        adjustment = {
            "action": reminder_adjustments.ACTION_POSTPONE,
            "days": 2,
            "reason": "Light rain expected (0.3 inches).",
            "details": {"precipitation_inches": 0.3}
        }

        result = reminder_adjustments.create_suggestion_notification(
            reminder, adjustment
        )

        assert result["reminder_id"] == "r1"
        assert result["plant_name"] == "Tomato Plant"
        assert result["suggestion_type"] == "postpone_watering"
        assert "postponing" in result["message"].lower()
        assert "2 days" in result["message"]
        assert result["action_label"] == "Postpone 2 days"
        assert result["days"] == 2

    def test_creates_advance_notification(self):
        """Should create notification for advance action."""
        reminder = {
            "id": "r2",
            "plant_name": "Rose Bush",
            "reminder_type": "watering"
        }

        adjustment = {
            "action": reminder_adjustments.ACTION_ADVANCE,
            "days": -1,
            "reason": "Extreme heat expected."
        }

        result = reminder_adjustments.create_suggestion_notification(
            reminder, adjustment
        )

        assert result["suggestion_type"] == "advance_watering"
        assert "advancing" in result["message"].lower()
        assert result["action_label"] == "Advance 1 day"
        assert result["days"] == -1


class TestGetAdjustmentSuggestions:
    """Test suggestion collection."""

    @patch('app.services.reminder_adjustments.evaluate_reminder_adjustment')
    def test_collects_suggestion_mode_adjustments(self, mock_evaluate):
        """Should collect all suggestion-mode adjustments."""
        mock_evaluate.return_value = {
            "action": reminder_adjustments.ACTION_POSTPONE,
            "mode": reminder_adjustments.MODE_SUGGESTION,
            "days": 1,
            "reason": "Light rain expected"
        }

        reminders = [
            {"id": "r1", "plant_id": "p1", "reminder_type": "watering", "plant_name": "Plant 1"},
            {"id": "r2", "plant_id": "p2", "reminder_type": "watering", "plant_name": "Plant 2"}
        ]

        plants = {
            "p1": {"location": "outdoor_bed", "species": "Test1"},
            "p2": {"location": "outdoor_bed", "species": "Test2"}
        }

        result = reminder_adjustments.get_adjustment_suggestions(
            reminders, plants, "Seattle, WA"
        )

        assert len(result) == 2
        assert all("message" in s for s in result)
        assert all("action_label" in s for s in result)

    @patch('app.services.reminder_adjustments.evaluate_reminder_adjustment')
    def test_excludes_automatic_adjustments(self, mock_evaluate):
        """Should not include automatic adjustments in suggestions."""
        mock_evaluate.return_value = {
            "action": reminder_adjustments.ACTION_POSTPONE,
            "mode": reminder_adjustments.MODE_AUTOMATIC,  # Automatic, not suggestion
            "days": 2,
            "reason": "Heavy rain"
        }

        reminders = [
            {"id": "r1", "plant_id": "p1", "reminder_type": "watering"}
        ]

        plants = {
            "p1": {"location": "outdoor_bed", "species": "Test"}
        }

        result = reminder_adjustments.get_adjustment_suggestions(
            reminders, plants, "Seattle, WA"
        )

        assert len(result) == 0  # Automatic adjustments not in suggestions
