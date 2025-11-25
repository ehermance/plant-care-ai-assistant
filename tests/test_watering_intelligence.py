"""
Unit tests for Watering Intelligence Service (app/services/watering_intelligence.py).

Tests stress-based watering logic, eligibility checks, and intelligent
watering recommendations adapted from Universal Watering Logic.
"""

import pytest
from app.services import watering_intelligence


class TestCheckWateringEligibility:
    """Test eligibility checks for watering recommendations."""

    def test_eligible_after_48_hours(self):
        eligible, reason = watering_intelligence.check_watering_eligibility(
            hours_since_watered=50,
            recent_rain=False,
            rain_expected=False,
            in_skip_window=False
        )
        assert eligible is True
        assert reason is None

    def test_not_eligible_before_48_hours(self):
        eligible, reason = watering_intelligence.check_watering_eligibility(
            hours_since_watered=30,
            recent_rain=False,
            rain_expected=False,
            in_skip_window=False
        )
        assert eligible is False
        assert "Last watered 30.0h ago" in reason
        assert "wait 18.0h more" in reason

    def test_not_eligible_recent_rain(self):
        eligible, reason = watering_intelligence.check_watering_eligibility(
            hours_since_watered=60,
            recent_rain=True,
            rain_expected=False,
            in_skip_window=False
        )
        assert eligible is False
        assert "Recent rain" in reason

    def test_not_eligible_rain_expected(self):
        eligible, reason = watering_intelligence.check_watering_eligibility(
            hours_since_watered=60,
            recent_rain=False,
            rain_expected=True,
            in_skip_window=False
        )
        assert eligible is False
        assert "Rain expected" in reason

    def test_not_eligible_skip_window(self):
        eligible, reason = watering_intelligence.check_watering_eligibility(
            hours_since_watered=60,
            recent_rain=False,
            rain_expected=False,
            in_skip_window=True
        )
        assert eligible is False
        assert "post-rain skip window" in reason

    def test_first_watering_always_eligible(self):
        eligible, reason = watering_intelligence.check_watering_eligibility(
            hours_since_watered=None,
            recent_rain=False,
            rain_expected=False,
            in_skip_window=False
        )
        assert eligible is True
        assert reason is None


class TestCalculateStressScore:
    """Test environmental stress score calculation."""

    def test_heat_stress_mild(self):
        weather = {
            "temp_f": 83,
            "humidity": 50,
            "wind_mph": 5,
            "dewpoint": 55,
            "conditions": "cloudy"
        }
        result = watering_intelligence.calculate_stress_score(weather)
        assert result["total_score"] == 1
        assert result["breakdown"]["heat"] == 1
        assert "warm (83°F)" in result["factors"]

    def test_heat_stress_moderate(self):
        weather = {
            "temp_f": 89,
            "humidity": 50,
            "wind_mph": 5,
            "dewpoint": 55,
            "conditions": "cloudy"
        }
        result = watering_intelligence.calculate_stress_score(weather)
        assert result["breakdown"]["heat"] == 2
        assert "hot (89°F)" in result["factors"]

    def test_heat_stress_severe(self):
        weather = {
            "temp_f": 95,
            "humidity": 50,
            "wind_mph": 5,
            "dewpoint": 55,
            "conditions": "cloudy"
        }
        result = watering_intelligence.calculate_stress_score(weather)
        assert result["breakdown"]["heat"] == 3
        assert "very hot (95°F)" in result["factors"]

    def test_wind_stress_outdoor_plants(self):
        weather = {
            "temp_f": 75,
            "humidity": 50,
            "wind_mph": 22,
            "dewpoint": 55,
            "conditions": "clear"
        }
        result = watering_intelligence.calculate_stress_score(
            weather,
            plant_type="outdoor_shrub"
        )
        assert result["breakdown"]["wind"] == 1
        assert "breezy (22mph)" in result["factors"]

    def test_wind_stress_not_applied_to_houseplants(self):
        weather = {
            "temp_f": 75,
            "humidity": 50,
            "wind_mph": 30,
            "dewpoint": 55,
            "conditions": "clear"
        }
        result = watering_intelligence.calculate_stress_score(
            weather,
            plant_type="houseplant"
        )
        assert result["breakdown"]["wind"] == 0

    def test_dry_spell_outdoor_plants(self):
        weather = {
            "temp_f": 75,
            "humidity": 50,
            "wind_mph": 5,
            "dewpoint": 55,
            "conditions": "clear"
        }
        result = watering_intelligence.calculate_stress_score(
            weather,
            hours_since_rain=180,  # 7.5 days
            plant_type="outdoor_shrub"
        )
        assert result["breakdown"]["dry_spell"] == 2

    def test_air_dryness_dewpoint(self):
        weather = {
            "temp_f": 75,
            "humidity": 50,
            "wind_mph": 5,
            "dewpoint": 40,
            "conditions": "clear"
        }
        result = watering_intelligence.calculate_stress_score(weather)
        assert result["breakdown"]["air_dryness"] == 1
        assert "dry air (dewpoint 40°F)" in result["factors"]

    def test_air_dryness_humidity(self):
        weather = {
            "temp_f": 75,
            "humidity": 20,
            "wind_mph": 5,
            "dewpoint": 55,
            "conditions": "clear"
        }
        result = watering_intelligence.calculate_stress_score(weather)
        assert result["breakdown"]["air_dryness"] == 1
        assert "low humidity (20%)" in result["factors"]

    def test_sun_et_boost(self):
        weather = {
            "temp_f": 90,
            "humidity": 50,
            "wind_mph": 5,
            "dewpoint": 55,
            "conditions": "clear"
        }
        result = watering_intelligence.calculate_stress_score(weather)
        # Heat: 2 + Sun/ET: 2 = 4 total
        assert result["total_score"] >= 4
        assert result["breakdown"]["sun_et"] == 2

    def test_wildflower_extra_heat_sensitivity(self):
        weather = {
            "temp_f": 93,
            "humidity": 50,
            "wind_mph": 5,
            "dewpoint": 55,
            "conditions": "cloudy"
        }
        result = watering_intelligence.calculate_stress_score(
            weather,
            plant_type="outdoor_wildflower"
        )
        assert result["breakdown"]["heat"] == 4  # +1 extra for wildflowers

    def test_germination_extra_sensitivity(self):
        weather = {
            "temp_f": 75,
            "humidity": 50,
            "wind_mph": 18,
            "dewpoint": 55,
            "conditions": "clear"
        }
        result = watering_intelligence.calculate_stress_score(
            weather,
            plant_type="outdoor_wildflower",
            plant_age_weeks=2
        )
        # Should have extra wind and ET points for germination
        assert result["total_score"] >= 2

    def test_combined_stress_factors(self):
        weather = {
            "temp_f": 95,
            "humidity": 15,
            "wind_mph": 28,
            "dewpoint": 30,
            "conditions": "clear"
        }
        result = watering_intelligence.calculate_stress_score(
            weather,
            plant_type="outdoor_shrub"
        )
        # Should have multiple contributing factors
        assert result["total_score"] >= 8
        assert len(result["factors"]) >= 4


class TestDetermineWateringRecommendation:
    """Test watering recommendation thresholds."""

    def test_houseplant_threshold(self):
        should_water, explanation = watering_intelligence.determine_watering_recommendation(
            stress_score=2,
            plant_type="houseplant"
        )
        assert should_water is True
        assert "threshold: 2" in explanation

    def test_houseplant_below_threshold(self):
        should_water, explanation = watering_intelligence.determine_watering_recommendation(
            stress_score=1,
            plant_type="houseplant"
        )
        assert should_water is False

    def test_shrub_threshold(self):
        should_water, explanation = watering_intelligence.determine_watering_recommendation(
            stress_score=2,
            plant_type="outdoor_shrub"
        )
        assert should_water is True

    def test_wildflower_germination_threshold(self):
        # Germination (weeks 1-3): threshold = 2
        should_water, explanation = watering_intelligence.determine_watering_recommendation(
            stress_score=2,
            plant_type="outdoor_wildflower",
            plant_age_weeks=2
        )
        assert should_water is True

    def test_wildflower_established_threshold(self):
        # Established (week 4+): threshold = 3
        should_water, explanation = watering_intelligence.determine_watering_recommendation(
            stress_score=2,
            plant_type="outdoor_wildflower",
            plant_age_weeks=5
        )
        assert should_water is False

        should_water, explanation = watering_intelligence.determine_watering_recommendation(
            stress_score=3,
            plant_type="outdoor_wildflower",
            plant_age_weeks=5
        )
        assert should_water is True


class TestGenerateWateringRecommendation:
    """Test complete watering recommendation generation."""

    def test_not_eligible_recent_watering(self):
        weather = {
            "temp_f": 95,
            "humidity": 20,
            "wind_mph": 25,
            "dewpoint": 35,
            "conditions": "clear"
        }
        result = watering_intelligence.generate_watering_recommendation(
            plant_name="Monstera",
            hours_since_watered=30,  # Too recent
            weather=weather,
            plant_type="houseplant"
        )
        assert result["should_water"] is False
        assert result["eligible"] is False
        assert "Last watered 30.0h ago" in result["reason"]

    def test_eligible_and_high_stress(self):
        weather = {
            "temp_f": 95,
            "humidity": 20,
            "wind_mph": 5,
            "dewpoint": 35,
            "conditions": "clear"
        }
        result = watering_intelligence.generate_watering_recommendation(
            plant_name="Monstera",
            hours_since_watered=60,
            weather=weather,
            plant_type="houseplant"
        )
        assert result["should_water"] is True
        assert result["eligible"] is True
        assert "💧" in result["recommendation"]
        assert "YES" in result["recommendation"]
        assert result["stress_score"] >= 2

    def test_eligible_but_low_stress(self):
        weather = {
            "temp_f": 70,
            "humidity": 50,
            "wind_mph": 5,
            "dewpoint": 55,
            "conditions": "cloudy"
        }
        result = watering_intelligence.generate_watering_recommendation(
            plant_name="Monstera",
            hours_since_watered=60,
            weather=weather,
            plant_type="houseplant"
        )
        assert result["should_water"] is False
        assert result["eligible"] is True
        assert "NOT YET" in result["recommendation"]

    def test_never_watered_no_weather(self):
        result = watering_intelligence.generate_watering_recommendation(
            plant_name="Monstera",
            hours_since_watered=None,
            weather=None,
            plant_type="houseplant"
        )
        assert result["should_water"] is True
        assert "CHECK SOIL" in result["recommendation"]

    def test_long_time_no_weather(self):
        result = watering_intelligence.generate_watering_recommendation(
            plant_name="Monstera",
            hours_since_watered=200,  # >7 days
            weather=None,
            plant_type="houseplant"
        )
        assert result["should_water"] is True
        assert "LIKELY YES" in result["recommendation"]

    def test_includes_top_stress_factors(self):
        weather = {
            "temp_f": 95,
            "humidity": 15,
            "wind_mph": 28,
            "dewpoint": 30,
            "conditions": "clear"
        }
        result = watering_intelligence.generate_watering_recommendation(
            plant_name="Monstera",
            hours_since_watered=60,
            weather=weather,
            plant_type="outdoor_shrub"
        )
        assert result["should_water"] is True
        assert len(result["stress_factors"]) > 0
        # Recommendation should include top factors
        recommendation_text = result["recommendation"]
        assert "very hot" in recommendation_text or "extremely low" in recommendation_text


class TestGetWateringInstructions:
    """Test watering instruction generation."""

    def test_houseplant_instructions(self):
        instructions = watering_intelligence.get_watering_instructions("houseplant")
        assert "thoroughly" in instructions.lower()
        assert "drainage" in instructions.lower()

    def test_outdoor_shrub_instructions(self):
        instructions = watering_intelligence.get_watering_instructions("outdoor_shrub")
        assert "deep soak" in instructions.lower()
        assert "root zone" in instructions.lower()

    def test_outdoor_wildflower_instructions(self):
        instructions = watering_intelligence.get_watering_instructions("outdoor_wildflower")
        assert "AM" in instructions
        assert "PM" in instructions

    def test_wildflower_windy_adjustment(self):
        weather = {
            "temp_f": 75,
            "humidity": 50,
            "wind_mph": 15,
            "dewpoint": 55,
            "conditions": "clear"
        }
        instructions = watering_intelligence.get_watering_instructions(
            "outdoor_wildflower",
            weather
        )
        assert "mulch" in instructions.lower()

    def test_wildflower_humid_adjustment(self):
        weather = {
            "temp_f": 75,
            "humidity": 50,
            "wind_mph": 5,
            "dewpoint": 68,
            "conditions": "cloudy"
        }
        instructions = watering_intelligence.get_watering_instructions(
            "outdoor_wildflower",
            weather
        )
        assert "pinched" in instructions.lower() or "surface dry" in instructions.lower()
