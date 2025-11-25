"""
Unit tests for AI Insights Service (app/services/ai_insights.py).

Tests pattern recognition, health trend analysis, weather context extraction,
and care completeness analysis for personalized AI recommendations.
"""

import pytest
from datetime import datetime, timedelta
from app.services import ai_insights


class TestExtractHealthKeywords:
    """Test health keyword extraction from user notes."""

    def test_extracts_yellow_leaves(self):
        text = "Leaves are yellowing at the tips"
        keywords = ai_insights.extract_health_keywords(text)
        assert "yellow_leaves" in keywords

    def test_extracts_brown_tips(self):
        text = "Tips are browning badly"
        keywords = ai_insights.extract_health_keywords(text)
        assert "brown_tips" in keywords

    def test_extracts_droopy(self):
        text = "Plant is drooping and looks sad"
        keywords = ai_insights.extract_health_keywords(text)
        assert "droopy" in keywords

    def test_extracts_pest_spotted(self):
        text = "Found aphids on the leaves"
        keywords = ai_insights.extract_health_keywords(text)
        assert "pest_spotted" in keywords

    def test_extracts_overwatered(self):
        text = "Soil is soggy and root rot might be starting"
        keywords = ai_insights.extract_health_keywords(text)
        assert "overwatered" in keywords

    def test_extracts_positive_keywords(self):
        text = "New growth appearing! Plant is thriving"
        keywords = ai_insights.extract_health_keywords(text)
        assert "new_growth" in keywords
        assert "thriving" in keywords

    def test_extracts_flowering(self):
        text = "Beautiful flowers blooming"
        keywords = ai_insights.extract_health_keywords(text)
        assert "flowering" in keywords

    def test_handles_empty_text(self):
        keywords = ai_insights.extract_health_keywords("")
        assert keywords == []

    def test_handles_none(self):
        keywords = ai_insights.extract_health_keywords(None)
        assert keywords == []

    def test_case_insensitive(self):
        text = "YELLOW LEAVES AND WILTING"
        keywords = ai_insights.extract_health_keywords(text)
        assert "yellow_leaves" in keywords
        assert "wilting" in keywords


class TestCalculateWateringPattern:
    """Test watering pattern analysis from activity history."""

    def test_regular_watering_pattern(self):
        activities = [
            {"action_type": "water", "action_at": "2025-01-01T10:00:00Z"},
            {"action_type": "water", "action_at": "2025-01-05T10:00:00Z"},
            {"action_type": "water", "action_at": "2025-01-09T10:00:00Z"},
        ]
        pattern = ai_insights.calculate_watering_pattern(activities)
        assert pattern["avg_interval_days"] == 4.0
        assert pattern["consistency"] == "regular"
        assert pattern["sample_size"] == 2

    def test_irregular_watering_pattern(self):
        activities = [
            {"action_type": "water", "action_at": "2025-01-01T10:00:00Z"},
            {"action_type": "water", "action_at": "2025-01-03T10:00:00Z"},  # 2 days
            {"action_type": "water", "action_at": "2025-01-10T10:00:00Z"},  # 7 days
        ]
        pattern = ai_insights.calculate_watering_pattern(activities)
        assert pattern["avg_interval_days"] == 4.5
        assert pattern["consistency"] == "irregular"

    def test_insufficient_data(self):
        activities = [
            {"action_type": "water", "action_at": "2025-01-01T10:00:00Z"},
        ]
        pattern = ai_insights.calculate_watering_pattern(activities)
        assert pattern["avg_interval_days"] is None
        assert pattern["consistency"] == "insufficient_data"
        assert pattern["sample_size"] == 0

    def test_filters_non_water_actions(self):
        activities = [
            {"action_type": "fertilize", "action_at": "2025-01-01T10:00:00Z"},
            {"action_type": "water", "action_at": "2025-01-02T10:00:00Z"},
            {"action_type": "water", "action_at": "2025-01-06T10:00:00Z"},
            {"action_type": "note", "action_at": "2025-01-07T10:00:00Z"},
        ]
        pattern = ai_insights.calculate_watering_pattern(activities)
        assert pattern["avg_interval_days"] == 4.0
        assert pattern["sample_size"] == 1

    def test_trend_detection_increasing_frequency(self):
        # Watering more frequently over time (shorter intervals)
        activities = [
            {"action_type": "water", "action_at": "2025-01-01T10:00:00Z"},
            {"action_type": "water", "action_at": "2025-01-08T10:00:00Z"},  # 7 days
            {"action_type": "water", "action_at": "2025-01-15T10:00:00Z"},  # 7 days
            {"action_type": "water", "action_at": "2025-01-18T10:00:00Z"},  # 3 days
            {"action_type": "water", "action_at": "2025-01-21T10:00:00Z"},  # 3 days
        ]
        pattern = ai_insights.calculate_watering_pattern(activities)
        assert pattern["recent_trend"] == "increasing_frequency"

    def test_trend_detection_decreasing_frequency(self):
        # Watering less frequently over time (longer intervals)
        activities = [
            {"action_type": "water", "action_at": "2025-01-01T10:00:00Z"},
            {"action_type": "water", "action_at": "2025-01-04T10:00:00Z"},  # 3 days
            {"action_type": "water", "action_at": "2025-01-07T10:00:00Z"},  # 3 days
            {"action_type": "water", "action_at": "2025-01-14T10:00:00Z"},  # 7 days
            {"action_type": "water", "action_at": "2025-01-21T10:00:00Z"},  # 7 days
        ]
        pattern = ai_insights.calculate_watering_pattern(activities)
        assert pattern["recent_trend"] == "decreasing_frequency"

    def test_empty_activities(self):
        pattern = ai_insights.calculate_watering_pattern([])
        assert pattern["consistency"] == "insufficient_data"


class TestIdentifyHealthTrends:
    """Test health trend identification from journal observations."""

    def test_identifies_recent_concerns(self):
        activities = [
            {"days_ago": 2, "notes": "Leaves are yellowing"},
            {"days_ago": 5, "notes": "Some brown tips appearing"},
        ]
        trends = ai_insights.identify_health_trends(activities)
        assert "yellow_leaves" in trends["recent_concerns"]
        assert "brown_tips" in trends["recent_concerns"]

    def test_detects_improving_trend(self):
        activities = [
            {"days_ago": 2, "notes": "Plant looks healthier now"},
            {"days_ago": 10, "notes": "Leaves are yellowing badly"},
            {"days_ago": 12, "notes": "Very droopy today"},
        ]
        trends = ai_insights.identify_health_trends(activities)
        assert trends["improving"] is True
        assert trends["deteriorating"] is False

    def test_detects_deteriorating_trend(self):
        activities = [
            {"days_ago": 2, "notes": "Leaves yellowing now"},
            {"days_ago": 3, "notes": "Pest spotted today"},
            {"days_ago": 10, "notes": "Plant was doing great"},
        ]
        trends = ai_insights.identify_health_trends(activities)
        assert trends["improving"] is False
        assert trends["deteriorating"] is True

    def test_limits_timeline_to_5_entries(self):
        activities = [
            {"days_ago": i, "notes": f"Entry {i} with yellow leaves"}
            for i in range(10)
        ]
        trends = ai_insights.identify_health_trends(activities)
        assert len(trends["timeline"]) == 5

    def test_handles_empty_activities(self):
        trends = ai_insights.identify_health_trends([])
        assert trends["recent_concerns"] == []
        assert trends["total_observations"] == 0


class TestExtractWeatherContextSummary:
    """Test weather context extraction for AI prompts."""

    def test_hot_and_dry_conditions(self):
        weather = {
            "temp_f": 95,
            "humidity": 25,
            "wind_mph": 20,
            "conditions": "clear"
        }
        summary = ai_insights.extract_weather_context_summary(weather)
        assert "hot" in summary.lower()
        assert "dry" in summary.lower()
        assert "95°F" in summary
        assert "heat stress risk" in summary

    def test_freezing_risk(self):
        weather = {
            "temp_f": 32,
            "humidity": 60,
            "wind_mph": 5,
            "conditions": "cloudy"
        }
        summary = ai_insights.extract_weather_context_summary(weather)
        assert "freezing risk" in summary.lower()
        assert "protect outdoor plants" in summary

    def test_humid_conditions(self):
        weather = {
            "temp_f": 75,
            "humidity": 85,
            "wind_mph": 3,
            "conditions": "cloudy"
        }
        summary = ai_insights.extract_weather_context_summary(weather)
        assert "humid" in summary.lower()
        assert "fungal risk" in summary

    def test_windy_conditions(self):
        weather = {
            "temp_f": 70,
            "humidity": 50,
            "wind_mph": 28,
            "conditions": "partly cloudy"
        }
        summary = ai_insights.extract_weather_context_summary(weather)
        assert "windy" in summary.lower()
        assert "28mph" in summary

    def test_rain_expected(self):
        weather = {
            "temp_f": 68,
            "humidity": 70,
            "wind_mph": 8,
            "conditions": "rain showers"
        }
        summary = ai_insights.extract_weather_context_summary(weather)
        assert "rain" in summary.lower()
        assert "delay outdoor watering" in summary

    def test_handles_none_weather(self):
        summary = ai_insights.extract_weather_context_summary(None)
        assert summary is None

    def test_handles_empty_weather(self):
        summary = ai_insights.extract_weather_context_summary({})
        # Should return None if no significant conditions
        assert summary is None or summary == ""


class TestAnalyzeCareCompleteness:
    """Test care completeness analysis."""

    def test_excellent_care_level(self):
        plant_id = "plant-123"
        activities = [
            {
                "action_type": "water",
                "action_at": (datetime.now() - timedelta(days=3)).isoformat()
            },
            {
                "action_type": "fertilize",
                "action_at": (datetime.now() - timedelta(days=7)).isoformat()
            },
        ]
        reminders = [
            {"reminder_type": "watering", "is_active": True},
            {"reminder_type": "fertilizing", "is_active": True},
        ]

        result = ai_insights.analyze_care_completeness(plant_id, activities, reminders)
        assert result["care_level"] == "excellent"
        assert result["on_schedule"] is True
        assert result["completion_rate"] == 1.0

    def test_good_care_level(self):
        plant_id = "plant-123"
        activities = [
            {
                "action_type": "water",
                "action_at": (datetime.now() - timedelta(days=3)).isoformat()
            },
        ]
        reminders = [
            {"reminder_type": "watering", "is_active": True},
            {"reminder_type": "fertilizing", "is_active": True},
        ]

        result = ai_insights.analyze_care_completeness(plant_id, activities, reminders)
        assert result["care_level"] == "needs_attention"
        assert result["completion_rate"] == 0.5

    def test_identifies_missed_care_types(self):
        plant_id = "plant-123"
        activities = [
            {
                "action_type": "water",
                "action_at": (datetime.now() - timedelta(days=3)).isoformat()
            },
        ]
        reminders = [
            {"reminder_type": "watering", "is_active": True},
            {"reminder_type": "fertilizing", "is_active": True},
            {"reminder_type": "misting", "is_active": True},
        ]

        result = ai_insights.analyze_care_completeness(plant_id, activities, reminders)
        assert "fertilizing" in result["missed_care_types"]
        assert "misting" in result["missed_care_types"]

    def test_handles_no_reminders(self):
        plant_id = "plant-123"
        result = ai_insights.analyze_care_completeness(plant_id, [], [])
        assert result["care_level"] == "unknown"
        assert result["completion_rate"] is None


class TestSummarizeRecentObservations:
    """Test recent observation summarization."""

    def test_prioritizes_recent_concerns(self):
        activities = [
            {
                "days_ago": 2,
                "action_type": "note",
                "notes": "Yellow leaves spotted"
            },
            {
                "days_ago": 5,
                "action_type": "note",
                "notes": "Looking great"
            },
            {
                "days_ago": 10,
                "action_type": "note",
                "notes": "Some brown tips"
            },
        ]

        observations = ai_insights.summarize_recent_observations(activities, max_observations=3)

        # Recent concern should be first
        assert observations[0]["days_ago"] == 2
        assert observations[0]["has_concern"] is True

    def test_limits_to_max_observations(self):
        activities = [
            {"days_ago": i, "action_type": "note", "notes": f"Note {i}"}
            for i in range(10)
        ]

        observations = ai_insights.summarize_recent_observations(activities, max_observations=3)
        assert len(observations) == 3

    def test_filters_empty_notes(self):
        activities = [
            {"days_ago": 1, "action_type": "water", "notes": None},
            {"days_ago": 2, "action_type": "note", "notes": "Has notes"},
            {"days_ago": 3, "action_type": "water", "notes": ""},
        ]

        observations = ai_insights.summarize_recent_observations(activities)
        assert len(observations) == 1
        assert observations[0]["days_ago"] == 2

    def test_truncates_long_notes(self):
        long_note = "A" * 200
        activities = [
            {"days_ago": 1, "action_type": "note", "notes": long_note}
        ]

        observations = ai_insights.summarize_recent_observations(activities)
        assert len(observations[0]["note_preview"]) == 100
