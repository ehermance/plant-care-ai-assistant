"""
Unit tests for weather intelligence enhancements (app/services/weather.py).

Tests for weather-aware reminder functionality including precipitation forecasts,
temperature extremes, seasonal pattern detection, and hardiness zone inference.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from app.services import weather


class TestGetPrecipitationLast48h:
    """Test historical precipitation tracking."""

    def test_returns_none_free_tier_limitation(self):
        """OpenWeather free tier doesn't include historical data."""
        result = weather.get_precipitation_last_48h("Seattle, WA")
        assert result is None

    def test_handles_none_city(self):
        result = weather.get_precipitation_last_48h(None)
        assert result is None


class TestGetPrecipitationForecast24h:
    """Test 24-hour precipitation forecasting."""

    @patch('app.services.weather.requests.get')
    @patch('app.services.weather._coords_for')
    @patch('app.services.weather._get_api_key')
    def test_calculates_total_precipitation(self, mock_key, mock_coords, mock_get):
        """Should sum precipitation from forecast periods."""
        mock_key.return_value = "test-key"
        mock_coords.return_value = (47.6062, -122.3321, -28800, "Seattle")

        # Mock forecast response with rain data
        now = datetime.now(timezone.utc)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "list": [
                {
                    "dt": int((now + timedelta(hours=3)).timestamp()),
                    "rain": {"3h": 5.0}  # 5mm in 3 hours
                },
                {
                    "dt": int((now + timedelta(hours=6)).timestamp()),
                    "rain": {"3h": 3.0}  # 3mm in 3 hours
                },
                {
                    "dt": int((now + timedelta(hours=9)).timestamp()),
                    "snow": {"3h": 2.0}  # 2mm snow
                }
            ]
        }
        mock_get.return_value = mock_response

        result = weather.get_precipitation_forecast_24h("Seattle, WA")

        # Total: 5 + 3 + 2 = 10mm = 0.39 inches
        assert result is not None
        assert result == pytest.approx(0.39, abs=0.01)

    @patch('app.services.weather.requests.get')
    @patch('app.services.weather._coords_for')
    @patch('app.services.weather._get_api_key')
    def test_handles_no_precipitation(self, mock_key, mock_coords, mock_get):
        """Should return 0.0 when no rain/snow in forecast."""
        mock_key.return_value = "test-key"
        mock_coords.return_value = (47.6062, -122.3321, -28800, "Seattle")

        now = datetime.now(timezone.utc)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "list": [
                {"dt": int((now + timedelta(hours=3)).timestamp())},
                {"dt": int((now + timedelta(hours=6)).timestamp())}
            ]
        }
        mock_get.return_value = mock_response

        result = weather.get_precipitation_forecast_24h("Seattle, WA")
        assert result == 0.0

    def test_handles_none_city(self):
        result = weather.get_precipitation_forecast_24h(None)
        assert result is None

    @patch('app.services.weather._get_api_key')
    def test_handles_missing_api_key(self, mock_key):
        mock_key.return_value = None
        result = weather.get_precipitation_forecast_24h("Seattle, WA")
        assert result is None


class TestGetTemperatureExtremesForecast:
    """Test temperature extreme forecasting."""

    @patch('app.services.weather.requests.get')
    @patch('app.services.weather._coords_for')
    @patch('app.services.weather._get_api_key')
    def test_finds_min_max_temperatures(self, mock_key, mock_coords, mock_get):
        """Should identify minimum and maximum temperatures in forecast."""
        mock_key.return_value = "test-key"
        mock_coords.return_value = (47.6062, -122.3321, -28800, "Seattle")

        now = datetime.now(timezone.utc)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "list": [
                {
                    "dt": int((now + timedelta(hours=3)).timestamp()),
                    "main": {"temp": 10.0}  # 50°F
                },
                {
                    "dt": int((now + timedelta(hours=6)).timestamp()),
                    "main": {"temp": 0.0}  # 32°F (freeze!)
                },
                {
                    "dt": int((now + timedelta(hours=9)).timestamp()),
                    "main": {"temp": 20.0}  # 68°F
                }
            ]
        }
        mock_get.return_value = mock_response

        result = weather.get_temperature_extremes_forecast("Seattle, WA", hours=12)

        assert result is not None
        assert result["temp_min_f"] == 32.0
        assert result["temp_max_f"] == 68.0
        assert result["temp_min_c"] == 0.0
        assert result["temp_max_c"] == 20.0
        assert result["freeze_risk"] is True

    @patch('app.services.weather.requests.get')
    @patch('app.services.weather._coords_for')
    @patch('app.services.weather._get_api_key')
    def test_no_freeze_risk_above_32f(self, mock_key, mock_coords, mock_get):
        """Freeze risk should be False when temps stay above 32°F."""
        mock_key.return_value = "test-key"
        mock_coords.return_value = (47.6062, -122.3321, -28800, "Seattle")

        now = datetime.now(timezone.utc)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "list": [
                {
                    "dt": int((now + timedelta(hours=3)).timestamp()),
                    "main": {"temp": 15.0}  # 59°F
                },
                {
                    "dt": int((now + timedelta(hours=6)).timestamp()),
                    "main": {"temp": 20.0}  # 68°F
                }
            ]
        }
        mock_get.return_value = mock_response

        result = weather.get_temperature_extremes_forecast("Seattle, WA", hours=12)

        assert result["freeze_risk"] is False

    def test_handles_none_city(self):
        result = weather.get_temperature_extremes_forecast(None)
        assert result is None


class TestGetSeasonalPattern:
    """Test seasonal pattern detection."""

    @patch('app.services.weather.get_temperature_extremes_forecast')
    @patch('app.services.weather.get_weather_for_city')
    def test_detects_summer_from_weather(self, mock_current, mock_extremes):
        """Should detect summer from high temperatures."""
        mock_current.return_value = {
            "temp_f": 85,
            "humidity": 60
        }
        mock_extremes.return_value = {
            "temp_min_f": 75,
            "temp_max_f": 95,
            "freeze_risk": False
        }

        result = weather.get_seasonal_pattern("Phoenix, AZ")

        assert result is not None
        assert result["season"] == "summer"
        assert result["is_dormancy_period"] is False
        assert result["frost_risk"] is False
        assert result["method"] == "weather"

    @patch('app.services.weather.get_temperature_extremes_forecast')
    @patch('app.services.weather.get_weather_for_city')
    def test_detects_winter_with_freeze_risk(self, mock_current, mock_extremes):
        """Should detect winter and set frost risk."""
        mock_current.return_value = {
            "temp_f": 35,
            "humidity": 70
        }
        mock_extremes.return_value = {
            "temp_min_f": 25,
            "temp_max_f": 40,
            "freeze_risk": True
        }

        result = weather.get_seasonal_pattern("Minneapolis, MN")

        assert result["season"] == "winter"
        assert result["is_dormancy_period"] is True
        assert result["frost_risk"] is True

    @patch('app.services.weather.get_temperature_extremes_forecast')
    @patch('app.services.weather.get_weather_for_city')
    def test_falls_back_to_calendar(self, mock_current, mock_extremes):
        """Should use calendar-based seasons when weather data unavailable."""
        mock_current.return_value = None
        mock_extremes.return_value = None

        result = weather.get_seasonal_pattern("Seattle, WA")

        assert result is not None
        assert result["season"] in ["winter", "spring", "summer", "fall"]
        assert result["method"] == "calendar"
        assert result["avg_temp_7d"] is None

    def test_handles_none_city(self):
        result = weather.get_seasonal_pattern(None)
        assert result is None


class TestInferHardinessZone:
    """Test USDA hardiness zone inference."""

    @patch('app.services.weather._coords_for')
    @patch('app.services.weather._get_api_key')
    def test_infers_zone_7a_for_mid_atlantic(self, mock_key, mock_coords):
        """Should infer zone 7a for mid-Atlantic latitudes (~39°N)."""
        mock_key.return_value = "test-key"
        mock_coords.return_value = (39.5, -76.6, -18000, "Baltimore")  # Baltimore, MD

        result = weather.infer_hardiness_zone("Baltimore, MD")

        assert result == "7a"

    @patch('app.services.weather._coords_for')
    @patch('app.services.weather._get_api_key')
    def test_infers_zone_9b_for_southern_florida(self, mock_key, mock_coords):
        """Should infer zone 9b for southern Florida (~26°N)."""
        mock_key.return_value = "test-key"
        mock_coords.return_value = (26.1, -80.1, -18000, "Fort Lauderdale")

        result = weather.infer_hardiness_zone("Fort Lauderdale, FL")

        assert result in ["9b", "10a"]  # Border region

    @patch('app.services.weather._coords_for')
    @patch('app.services.weather._get_api_key')
    def test_infers_zone_5a_for_northern_states(self, mock_key, mock_coords):
        """Should infer zone 5a for northern states (~45°N)."""
        mock_key.return_value = "test-key"
        mock_coords.return_value = (45.0, -93.0, -21600, "Minneapolis")

        result = weather.infer_hardiness_zone("Minneapolis, MN")

        assert result == "5a"

    @patch('app.services.weather._coords_for')
    @patch('app.services.weather._get_api_key')
    def test_infers_zone_10b_for_hawaii(self, mock_key, mock_coords):
        """Should infer zone 10b+ for Hawaii (~21°N)."""
        mock_key.return_value = "test-key"
        mock_coords.return_value = (21.3, -157.8, -36000, "Honolulu")

        result = weather.infer_hardiness_zone("Honolulu, HI")

        assert result in ["10b", "11a"]

    def test_handles_none_city(self):
        result = weather.infer_hardiness_zone(None)
        assert result is None

    @patch('app.services.weather._get_api_key')
    def test_handles_missing_api_key(self, mock_key):
        mock_key.return_value = None
        result = weather.infer_hardiness_zone("Seattle, WA")
        assert result is None


class TestIntegration:
    """Integration tests for weather intelligence functions."""

    @patch('app.services.weather.requests.get')
    @patch('app.services.weather._coords_for')
    @patch('app.services.weather._get_api_key')
    def test_seasonal_pattern_with_extremes(self, mock_key, mock_coords, mock_get):
        """Test seasonal pattern detection integrates with temperature extremes."""
        mock_key.return_value = "test-key"
        mock_coords.return_value = (47.6062, -122.3321, -28800, "Seattle")

        # Mock current weather
        now = datetime.now(timezone.utc)
        current_response = MagicMock()
        current_response.json.return_value = {
            "name": "Seattle",
            "main": {"temp": 10, "humidity": 80},  # 50°F
            "weather": [{"id": 800, "main": "Clear", "description": "clear sky"}],
            "wind": {"speed": 3}
        }

        # Mock forecast with spring-like temps
        forecast_response = MagicMock()
        forecast_response.json.return_value = {
            "list": [
                {
                    "dt": int((now + timedelta(hours=3)).timestamp()),
                    "main": {"temp": 12}  # 54°F
                },
                {
                    "dt": int((now + timedelta(hours=6)).timestamp()),
                    "main": {"temp": 15}  # 59°F
                }
            ]
        }

        mock_get.side_effect = [current_response, forecast_response]

        result = weather.get_seasonal_pattern("Seattle, WA")

        assert result is not None
        assert result["season"] in ["spring", "fall"]  # Depends on month
        assert result["method"] == "weather"
        assert result["frost_risk"] is False
