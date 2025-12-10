"""
Integration tests for weather-aware reminder adjustments.

Tests end-to-end flow from reminder fetching through adjustment application.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta
from app.services import reminders


class TestReminderAdjustmentIntegration:
    """Test end-to-end reminder adjustment flow."""

    @patch('app.services.supabase_client.get_admin_client')
    @patch('app.services.reminders.get_user_profile')
    @patch('app.services.reminders.get_due_reminders')
    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_heavy_rain_automatic_adjustment(
        self,
        mock_light,
        mock_chars,
        mock_seasonal,
        mock_temp,
        mock_precip,
        mock_weather,
        mock_get_due,
        mock_profile,
        mock_db
    ):
        """Heavy rain should trigger automatic postponement for outdoor plants.

        When automatically postponed to a future date, the reminder is EXCLUDED
        from adjusted_reminders (it's no longer due today).
        """
        # Setup user profile
        mock_profile.return_value = {"city": "Seattle, WA"}
        mock_db.return_value = None  # No actual DB writes

        # Setup reminders - due today, will be postponed to future
        mock_get_due.return_value = [
            {
                "id": "r1",
                "user_id": "user-123",
                "plant_id": "p1",
                "reminder_type": "watering",
                "next_due": date.today().isoformat(),
                "skip_weather_adjustment": False,
                "plants": {
                    "id": "p1",
                    "name": "Tomato Plant",
                    "location": "outdoor_bed",
                    "species": "Tomato"
                }
            }
        ]

        # Setup weather - heavy rain
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

        # Call integration function
        adjusted_reminders, suggestions = reminders.get_due_reminders_with_adjustments("user-123")

        # Reminder is automatically postponed to FUTURE, so it's EXCLUDED from Today's Tasks
        assert len(adjusted_reminders) == 0

        # Suggestions should be empty (automatic adjustment, not suggestion)
        assert len(suggestions) == 0

    @patch('app.services.reminders.get_user_profile')
    @patch('app.services.reminders.get_due_reminders')
    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_light_rain_suggestion(
        self,
        mock_light,
        mock_chars,
        mock_seasonal,
        mock_temp,
        mock_precip,
        mock_weather,
        mock_get_due,
        mock_profile
    ):
        """Light rain should create suggestion, not automatic adjustment."""
        mock_profile.return_value = {"city": "Portland, OR"}

        mock_get_due.return_value = [
            {
                "id": "r2",
                "plant_id": "p2",
                "reminder_type": "watering",
                "next_due": (date.today() + timedelta(days=1)).isoformat(),
                "skip_weather_adjustment": False,
                "plants": {
                    "id": "p2",
                    "name": "Lavender",
                    "location": "outdoor_potted",
                    "species": "Lavender"
                }
            }
        ]

        # Light rain
        mock_weather.return_value = {"temp_f": 65, "humidity": 70}
        mock_precip.return_value = 0.3  # Light rain
        mock_temp.return_value = {
            "temp_min_f": 55,
            "temp_max_f": 70,
            "freeze_risk": False
        }
        mock_seasonal.return_value = {"season": "spring", "is_dormancy_period": False}
        mock_chars.return_value = {"water_needs": "moderate"}
        mock_light.return_value = 1.0

        adjusted_reminders, suggestions = reminders.get_due_reminders_with_adjustments("user-123")

        # No automatic adjustment
        assert len(adjusted_reminders) == 1
        assert "adjustment" not in adjusted_reminders[0]

        # Should have suggestion
        assert len(suggestions) == 1
        assert "light rain" in suggestions[0]["message"].lower()
        assert suggestions[0]["suggestion_type"] == "postpone_watering"
        assert suggestions[0]["action_label"] == "Postpone 1 day"

    @patch('app.services.supabase_client.get_admin_client')
    @patch('app.services.reminders.get_user_profile')
    @patch('app.services.reminders.get_due_reminders')
    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_freeze_warning_highest_priority(
        self,
        mock_light,
        mock_chars,
        mock_seasonal,
        mock_temp,
        mock_precip,
        mock_weather,
        mock_get_due,
        mock_profile,
        mock_db
    ):
        """Freeze warnings should take priority over other adjustments.

        When automatically postponed to a future date, the reminder is EXCLUDED
        from adjusted_reminders (it's no longer due today).
        """
        mock_profile.return_value = {"city": "Minneapolis, MN"}
        mock_db.return_value = None  # No actual DB writes

        mock_get_due.return_value = [
            {
                "id": "r3",
                "user_id": "user-123",
                "plant_id": "p3",
                "reminder_type": "watering",
                "next_due": date.today().isoformat(),
                "skip_weather_adjustment": False,
                "plants": {
                    "id": "p3",
                    "name": "Shrub",
                    "location": "outdoor_bed",
                    "species": "Test"
                }
            }
        ]

        # Freeze warning + light rain (freeze should win)
        mock_weather.return_value = {"temp_f": 35, "humidity": 85}
        mock_precip.return_value = 0.3  # Light rain
        mock_temp.return_value = {
            "temp_min_f": 28,  # Freeze!
            "temp_max_f": 40,
            "freeze_risk": True
        }
        mock_seasonal.return_value = {"season": "winter", "is_dormancy_period": False}
        mock_chars.return_value = {"water_needs": "moderate"}
        mock_light.return_value = 1.0

        adjusted_reminders, suggestions = reminders.get_due_reminders_with_adjustments("user-123")

        # Freeze warning postpones to FUTURE, so reminder is EXCLUDED from Today's Tasks
        assert len(adjusted_reminders) == 0
        # Light rain suggestion should not appear (freeze took priority and postponed it)

    @patch('app.services.reminders.get_user_profile')
    @patch('app.services.reminders.get_due_reminders')
    def test_no_city_no_adjustments(self, mock_get_due, mock_profile):
        """Without city, no adjustments should be made."""
        mock_profile.return_value = {"city": None}  # No city

        mock_get_due.return_value = [
            {
                "id": "r4",
                "plant_id": "p4",
                "reminder_type": "watering",
                "next_due": (date.today() + timedelta(days=1)).isoformat(),
                "plants": {
                    "id": "p4",
                    "name": "Test",
                    "location": "outdoor_bed"
                }
            }
        ]

        adjusted_reminders, suggestions = reminders.get_due_reminders_with_adjustments("user-123")

        # No adjustments without city
        assert len(adjusted_reminders) == 1
        assert "adjustment" not in adjusted_reminders[0]
        assert len(suggestions) == 0

    @patch('app.services.reminders.get_user_profile')
    @patch('app.services.reminders.get_due_reminders')
    @patch('app.services.reminder_adjustments.get_weather_for_city')
    @patch('app.services.reminder_adjustments.get_precipitation_forecast_24h')
    @patch('app.services.reminder_adjustments.get_temperature_extremes_forecast')
    @patch('app.services.reminder_adjustments.get_seasonal_pattern')
    @patch('app.services.reminder_adjustments.infer_plant_characteristics')
    @patch('app.services.reminder_adjustments.get_light_adjustment_factor')
    def test_indoor_plant_ignores_rain(
        self,
        mock_light,
        mock_chars,
        mock_seasonal,
        mock_temp,
        mock_precip,
        mock_weather,
        mock_get_due,
        mock_profile
    ):
        """Indoor plants should not be affected by rain."""
        mock_profile.return_value = {"city": "Seattle, WA"}

        mock_get_due.return_value = [
            {
                "id": "r5",
                "plant_id": "p5",
                "reminder_type": "watering",
                "next_due": (date.today() + timedelta(days=1)).isoformat(),
                "skip_weather_adjustment": False,
                "plants": {
                    "id": "p5",
                    "name": "Monstera",
                    "location": "indoor_potted",  # Indoor!
                    "species": "Monstera"
                }
            }
        ]

        # Heavy rain
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

        adjusted_reminders, suggestions = reminders.get_due_reminders_with_adjustments("user-123")

        # Indoor plant should not get rain adjustment
        assert len(adjusted_reminders) == 1
        if "adjustment" in adjusted_reminders[0]:
            assert "rain" not in adjusted_reminders[0]["adjustment"]["reason"].lower()

        # No rain-related suggestions
        for s in suggestions:
            assert "rain" not in s["message"].lower()

    @patch('app.services.reminder_adjustments.apply_automatic_adjustments')
    @patch('app.services.reminders.get_user_profile')
    @patch('app.services.reminders.get_due_reminders')
    def test_multiple_reminders_mixed_adjustments(self, mock_get_due, mock_profile, mock_auto_adjust):
        """Multiple reminders should be handled independently."""
        mock_profile.return_value = {"city": "Seattle, WA"}

        test_reminders = [
            {
                "id": "r1",
                "plant_id": "p1",
                "reminder_type": "watering",
                "next_due": (date.today() + timedelta(days=1)).isoformat(),
                "skip_weather_adjustment": False,
                "plants": {
                    "id": "p1",
                    "name": "Plant 1",
                    "location": "outdoor_bed",
                    "species": "Test1"
                }
            },
            {
                "id": "r2",
                "plant_id": "p2",
                "reminder_type": "watering",
                "next_due": (date.today() + timedelta(days=1)).isoformat(),
                "skip_weather_adjustment": True,  # Opted out
                "plants": {
                    "id": "p2",
                    "name": "Plant 2",
                    "location": "outdoor_bed",
                    "species": "Test2"
                }
            },
            {
                "id": "r3",
                "plant_id": "p3",
                "reminder_type": "fertilizing",  # Not watering
                "next_due": (date.today() + timedelta(days=1)).isoformat(),
                "plants": {
                    "id": "p3",
                    "name": "Plant 3",
                    "location": "outdoor_bed"
                }
            }
        ]
        mock_get_due.return_value = test_reminders
        # Mock apply_automatic_adjustments to return all reminders unchanged
        # (no auto-postponements that would filter them out)
        mock_auto_adjust.return_value = test_reminders

        adjusted_reminders, suggestions = reminders.get_due_reminders_with_adjustments("user-123")

        # All reminders returned (no auto-postponements filtered them out)
        assert len(adjusted_reminders) == 3

        # Only first reminder eligible for adjustments
        # (second opted out, third is fertilizing)
