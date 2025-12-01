"""
Unit tests for plant intelligence service (app/services/plant_intelligence.py).

Tests AI-powered plant characteristic inference, light adjustment factors,
and caching behavior.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from app.services import plant_intelligence


class TestCacheManagement:
    """Test cache key generation and cache operations."""

    def test_cache_key_generation(self):
        """Should generate consistent cache keys for same plant data."""
        plant1 = {
            "species": "Monstera deliciosa",
            "location": "indoor_potted",
            "notes": "Loves bright indirect light",
            "light": "bright_indirect"
        }

        plant2 = {
            "species": "Monstera deliciosa",
            "location": "indoor_potted",
            "notes": "Loves bright indirect light",
            "light": "bright_indirect"
        }

        key1 = plant_intelligence._get_cache_key(plant1)
        key2 = plant_intelligence._get_cache_key(plant2)

        assert key1 == key2
        assert len(key1) == 32  # MD5 hash length

    def test_cache_key_differs_for_different_plants(self):
        """Different plant data should generate different cache keys."""
        plant1 = {"species": "Monstera deliciosa", "location": "indoor_potted"}
        plant2 = {"species": "Pothos", "location": "indoor_potted"}

        key1 = plant_intelligence._get_cache_key(plant1)
        key2 = plant_intelligence._get_cache_key(plant2)

        assert key1 != key2

    def test_cache_stores_and_retrieves_inference(self):
        """Should store and retrieve cached inference."""
        cache_key = "test-key-123"
        inference = {
            "origin": "native",
            "lifecycle": "perennial",
            "confidence": 0.9
        }

        plant_intelligence._cache_inference(cache_key, inference)
        cached = plant_intelligence._get_cached_inference(cache_key)

        assert cached is not None
        assert cached["origin"] == "native"
        assert cached["lifecycle"] == "perennial"
        assert cached["confidence"] == 0.9

    def test_cache_expiration(self):
        """Should return None for expired cache entries."""
        cache_key = "test-key-expired"
        inference = {"origin": "native", "confidence": 0.9}

        # Manually insert expired cache entry
        plant_intelligence._INFERENCE_CACHE[cache_key] = {
            "inference": inference,
            "cached_at": datetime.now(timezone.utc) - timedelta(days=8)  # 8 days ago (> 7 day cache)
        }

        cached = plant_intelligence._get_cached_inference(cache_key)
        assert cached is None
        assert cache_key not in plant_intelligence._INFERENCE_CACHE

    def test_clear_cache(self):
        """Should clear all cache entries."""
        plant_intelligence._INFERENCE_CACHE["key1"] = {"test": "data1"}
        plant_intelligence._INFERENCE_CACHE["key2"] = {"test": "data2"}

        plant_intelligence.clear_inference_cache()

        assert len(plant_intelligence._INFERENCE_CACHE) == 0


class TestInferPlantCharacteristics:
    """Test AI-powered plant characteristic inference."""

    def setup_method(self):
        """Clear cache before each test."""
        plant_intelligence.clear_inference_cache()

    @patch('app.services.plant_intelligence._infer_with_ai')
    def test_successful_ai_inference(self, mock_ai):
        """Should return AI inference when successful."""
        mock_ai.return_value = {
            "origin": "non_native_adapted",
            "lifecycle": "perennial",
            "cold_tolerance": "semi_hardy",
            "water_needs": "moderate",
            "dormancy_months": [11, 12, 1, 2],
            "confidence": 0.85
        }

        plant = {
            "species": "Monstera deliciosa",
            "location": "indoor_potted",
            "notes": "Tropical plant"
        }

        result = plant_intelligence.infer_plant_characteristics(plant, "Seattle, WA")

        assert result is not None
        assert result["origin"] == "non_native_adapted"
        assert result["lifecycle"] == "perennial"
        assert result["water_needs"] == "moderate"
        assert result["confidence"] == 0.85
        assert result["source"] == "ai"

    @patch('app.services.plant_intelligence._infer_with_ai')
    def test_caching_behavior(self, mock_ai):
        """Should use cache on second call for same plant."""
        mock_ai.return_value = {
            "origin": "native",
            "lifecycle": "perennial",
            "cold_tolerance": "hardy",
            "water_needs": "low",
            "dormancy_months": [],
            "confidence": 0.9
        }

        plant = {
            "species": "Douglas Fir",
            "location": "outdoor_bed",
            "notes": "Native evergreen"
        }

        # First call - should use AI
        result1 = plant_intelligence.infer_plant_characteristics(plant, "Seattle, WA")
        assert result1["source"] == "ai"
        assert mock_ai.call_count == 1

        # Second call - should use cache
        result2 = plant_intelligence.infer_plant_characteristics(plant, "Seattle, WA")
        assert result2["source"] == "cache"
        assert result2["origin"] == result1["origin"]
        assert mock_ai.call_count == 1  # Not called again

    @patch('app.services.plant_intelligence._infer_with_ai')
    def test_fallback_to_defaults(self, mock_ai):
        """Should return defaults when AI fails."""
        mock_ai.return_value = None  # AI failure

        plant = {
            "species": "Unknown Plant",
            "location": "indoor_potted"
        }

        result = plant_intelligence.infer_plant_characteristics(plant)

        assert result is not None
        assert result["origin"] == "non_native_adapted"
        assert result["lifecycle"] == "unknown"
        assert result["cold_tolerance"] == "semi_hardy"
        assert result["water_needs"] == "moderate"
        assert result["confidence"] == 0.3
        assert result["source"] == "default"

    @patch('app.services.ai._get_litellm_router')
    def test_ai_inference_with_valid_json(self, mock_router_fn):
        """Should parse valid JSON response from AI."""
        mock_router = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """{
            "origin": "native",
            "lifecycle": "perennial",
            "cold_tolerance": "hardy",
            "water_needs": "low",
            "dormancy_months": [11, 12, 1, 2],
            "confidence": 0.95
        }"""

        mock_router.completion.return_value = mock_response
        mock_router_fn.return_value = (mock_router, None)

        result = plant_intelligence._infer_with_ai(
            "Douglas Fir",
            "outdoor_bed",
            "Native tree",
            "Seattle, WA",
            "8a"
        )

        assert result is not None
        assert result["origin"] == "native"
        assert result["lifecycle"] == "perennial"
        assert result["confidence"] == 0.95

    @patch('app.services.ai._get_litellm_router')
    def test_ai_inference_with_markdown_wrapped_json(self, mock_router_fn):
        """Should extract JSON from markdown code blocks."""
        mock_router = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """```json
{
    "origin": "non_native_adapted",
    "lifecycle": "annual",
    "cold_tolerance": "tender",
    "water_needs": "high",
    "dormancy_months": [],
    "confidence": 0.75
}
```"""

        mock_router.completion.return_value = mock_response
        mock_router_fn.return_value = (mock_router, None)

        result = plant_intelligence._infer_with_ai(
            "Tomato",
            "outdoor_bed",
            "Summer vegetable",
            "Portland, OR",
            "8b"
        )

        assert result is not None
        assert result["origin"] == "non_native_adapted"
        assert result["lifecycle"] == "annual"
        assert result["water_needs"] == "high"

    @patch('app.services.ai._get_litellm_router')
    def test_ai_inference_validates_enums(self, mock_router_fn):
        """Should validate and fix invalid enum values."""
        mock_router = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        # Invalid values: "exotic" origin, "super_hardy" tolerance
        mock_response.choices[0].message.content = """{
            "origin": "exotic",
            "lifecycle": "perennial",
            "cold_tolerance": "super_hardy",
            "water_needs": "very_high",
            "dormancy_months": [11, 12, 1, 2],
            "confidence": 0.8
        }"""

        mock_router.completion.return_value = mock_response
        mock_router_fn.return_value = (mock_router, None)

        result = plant_intelligence._infer_with_ai(
            "Plant",
            "indoor_potted",
            None,
            "Seattle, WA",
            "8a"
        )

        assert result is not None
        # Should fix invalid values to safe defaults
        assert result["origin"] == "non_native_adapted"  # Fixed from "exotic"
        assert result["cold_tolerance"] == "semi_hardy"  # Fixed from "super_hardy"
        assert result["water_needs"] == "moderate"  # Fixed from "very_high"


class TestGetLightAdjustmentFactor:
    """Test light-based watering adjustment calculations."""

    def test_indoor_artificial_light_no_adjustment(self):
        """Indoor plants with grow lights should have no seasonal adjustment."""
        plant = {
            "location": "indoor_potted",
            "light": "bright_indirect",
            "notes": "Using LED grow light for 12 hours/day"
        }

        factor = plant_intelligence.get_light_adjustment_factor(plant)
        assert factor == 1.0

    def test_indoor_natural_light_summer(self):
        """Indoor natural light in summer should increase watering."""
        plant = {
            "location": "indoor_potted",
            "light": "bright_indirect",
            "notes": "Near south-facing window"
        }

        seasonal = {"season": "summer", "is_dormancy_period": False}

        factor = plant_intelligence.get_light_adjustment_factor(
            plant,
            seasonal_pattern=seasonal
        )

        assert factor == 1.1

    def test_indoor_natural_light_winter(self):
        """Indoor natural light in winter should decrease watering."""
        plant = {
            "location": "indoor_potted",
            "light": "bright_indirect",
            "notes": "Near window"
        }

        seasonal = {"season": "winter", "is_dormancy_period": False}

        factor = plant_intelligence.get_light_adjustment_factor(
            plant,
            seasonal_pattern=seasonal
        )

        assert factor == 0.9

    def test_outdoor_full_sun_summer(self):
        """Outdoor full sun in summer needs significant increase."""
        plant = {
            "location": "outdoor_bed",
            "light": "full_sun"
        }

        seasonal = {"season": "summer", "is_dormancy_period": False}

        factor = plant_intelligence.get_light_adjustment_factor(
            plant,
            seasonal_pattern=seasonal
        )

        assert factor == 1.3

    def test_outdoor_full_sun_winter(self):
        """Outdoor full sun in winter needs less water."""
        plant = {
            "location": "outdoor_potted",
            "light": "full_sun"
        }

        seasonal = {"season": "winter", "is_dormancy_period": False}

        factor = plant_intelligence.get_light_adjustment_factor(
            plant,
            seasonal_pattern=seasonal
        )

        assert factor == 0.9

    def test_outdoor_partial_sun(self):
        """Partial sun should have moderate adjustment."""
        plant = {
            "location": "outdoor_bed",
            "light": "partial_sun"
        }

        seasonal = {"season": "summer", "is_dormancy_period": False}

        factor = plant_intelligence.get_light_adjustment_factor(
            plant,
            seasonal_pattern=seasonal
        )

        assert factor == 1.1

    def test_outdoor_shade(self):
        """Shade plants need less water."""
        plant = {
            "location": "outdoor_bed",
            "light": "shade"
        }

        seasonal = {"season": "summer", "is_dormancy_period": False}

        factor = plant_intelligence.get_light_adjustment_factor(
            plant,
            seasonal_pattern=seasonal
        )

        assert factor == 0.8

    def test_dormancy_reduces_watering(self):
        """Dormant plants need much less water regardless of light."""
        plant = {
            "location": "outdoor_bed",
            "light": "full_sun"
        }

        seasonal = {"season": "winter", "is_dormancy_period": True}

        factor = plant_intelligence.get_light_adjustment_factor(
            plant,
            seasonal_pattern=seasonal
        )

        assert factor == 0.6

    def test_defaults_to_baseline(self):
        """Unknown light conditions should use baseline."""
        plant = {
            "location": "indoor_potted",
            "light": "unknown_light_type"
        }

        factor = plant_intelligence.get_light_adjustment_factor(plant)

        assert factor == 1.0

    def test_infers_season_from_weather(self):
        """Should infer season from weather when seasonal_pattern not provided."""
        plant = {
            "location": "outdoor_bed",
            "light": "full_sun"
        }

        weather = {"temp_f": 85}  # Summer temperature

        factor = plant_intelligence.get_light_adjustment_factor(
            plant,
            weather=weather
        )

        assert factor == 1.3  # Summer full sun


class TestDefaultInference:
    """Test default inference fallback."""

    def test_returns_conservative_defaults(self):
        """Should return safe conservative defaults."""
        result = plant_intelligence._get_default_inference("indoor_potted")

        assert result["origin"] == "non_native_adapted"
        assert result["lifecycle"] == "unknown"
        assert result["cold_tolerance"] == "semi_hardy"
        assert result["water_needs"] == "moderate"
        assert result["dormancy_months"] == []
        assert result["confidence"] == 0.3
        assert result["source"] == "default"
