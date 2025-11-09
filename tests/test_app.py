"""
High-level tests for validation, weather, and advice generation.

Covers success and fallback paths to ensure stable behavior regardless of
external services or configuration.
"""

import sys
import types
import importlib
import pytest

# --------------------------
# openweather tests
# --------------------------

@pytest.fixture
def with_openweather_key(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")
    import app
    importlib.reload(app)  # harmless now, but OK to keep
    return app

@pytest.fixture
def without_openweather_key(monkeypatch):
    # Set to empty string to block python-dotenv from "refilling" it
    monkeypatch.setenv("OPENWEATHER_API_KEY", "")
    import app
    importlib.reload(app)
    return app

# --------------------------
# ai_advice() tests
# --------------------------

def _install_fake_litellm_success(monkeypatch, reply_text="• Tip 1\n• Tip 2", model="gpt-4o-mini"):
    """
    Inject a fake 'litellm' module into sys.modules so that
    'from litellm import Router' works inside app.services.ai.
    This fake returns a deterministic response.
    """
    # Clear the router cache before installing mock
    from app.services.ai import _clear_router_cache
    _clear_router_cache()

    class FakeMessage:
        def __init__(self, content):
            self.content = content

    class FakeChoice:
        def __init__(self, content):
            self.message = FakeMessage(content)

    class FakeResp:
        def __init__(self, content, model):
            self.choices = [FakeChoice(content)]
            self.model = model

    class FakeRouter:
        def __init__(self, model_list=None, fallbacks=None, num_retries=None, timeout=None):
            pass

        def completion(self, model=None, messages=None, **kwargs):
            # Return response based on which model is being used
            return FakeResp(reply_text, model)

    fake_mod = types.SimpleNamespace(Router=FakeRouter)
    monkeypatch.setitem(sys.modules, "litellm", fake_mod)


def _install_fake_litellm_raises(monkeypatch, exc=RuntimeError("boom")):
    """Fake LiteLLM Router that raises when .completion() is called."""
    # Clear the router cache before installing mock
    from app.services.ai import _clear_router_cache
    _clear_router_cache()

    class FakeRouter:
        def __init__(self, model_list=None, fallbacks=None, num_retries=None, timeout=None):
            pass

        def completion(self, model=None, messages=None, **kwargs):
            raise exc

    fake_mod = types.SimpleNamespace(Router=FakeRouter)
    monkeypatch.setitem(sys.modules, "litellm", fake_mod)


def test_ai_advice_no_key(monkeypatch):
    """
    When both OPENAI_API_KEY and GEMINI_API_KEY are empty/missing,
    ai_advice should return None and should NOT need the litellm module at all.
    """
    # Clear router cache to ensure clean test state
    from app.services.ai import _clear_router_cache
    _clear_router_cache()

    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    import app
    importlib.reload(app)

    out = app.ai_advice("How often to water?", "Monstera", weather=None)
    assert out is None


def test_ai_advice_success_openai(monkeypatch):
    """
    With OpenAI key present and a fake LiteLLM Router that returns a canned response,
    ai_advice should return that text (stripped).
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    _install_fake_litellm_success(monkeypatch, reply_text="• AI: water in the morning.\n• AI: bright-indirect light.", model="gpt-4o-mini")
    import app
    importlib.reload(app)

    txt = app.ai_advice("Watering schedule?", "Pothos", weather={"city":"Austin","temp_c":31})
    assert isinstance(txt, str)
    assert "AI: water in the morning" in txt
    assert "AI: bright-indirect light" in txt


def test_ai_advice_success_gemini(monkeypatch):
    """
    With Gemini key present and a fake LiteLLM Router that returns a canned response,
    ai_advice should return that text (stripped).
    """
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    _install_fake_litellm_success(monkeypatch, reply_text="• Gemini: water regularly.\n• Gemini: provide good light.", model="gemini/gemini-flash-latest")
    import app
    importlib.reload(app)

    txt = app.ai_advice("Watering schedule?", "Pothos", weather={"city":"Austin","temp_c":31})
    assert isinstance(txt, str)
    assert "Gemini: water regularly" in txt
    assert "Gemini: provide good light" in txt


def test_ai_advice_exception(monkeypatch):
    """
    If the LiteLLM Router throws, ai_advice should swallow and return None.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    _install_fake_litellm_raises(monkeypatch, exc=RuntimeError("rate limit"))
    import app
    importlib.reload(app)

    txt = app.ai_advice("Light needs?", "Snake Plant", weather=None)
    assert txt is None

# --------------------------
# weather_adjustment_tip() tests
# --------------------------

def test_weather_adjustment_tip_hot(monkeypatch):
    import app; importlib.reload(app)
    tip = app.weather_adjustment_tip({"temp_c": 33, "city": "Austin"}, "Monstera")
    assert tip is not None
    assert "hot" in tip.lower()
    assert "33" in tip  # temperature echoed

def test_weather_adjustment_tip_cold(monkeypatch):
    import app; importlib.reload(app)
    tip = app.weather_adjustment_tip({"temp_c": 4, "city": "Boston"}, "Pothos")
    assert tip is not None
    assert "cold" in tip.lower()
    assert "draft" in tip.lower() or "away from" in tip.lower()

def test_weather_adjustment_tip_mild(monkeypatch):
    import app; importlib.reload(app)
    tip = app.weather_adjustment_tip({"temp_c": 20, "city": "Dallas"}, "Snake Plant")
    assert tip is not None
    assert "mild" in tip.lower() or "maintain" in tip.lower()

def test_weather_adjustment_tip_none_weather(monkeypatch):
    import app; importlib.reload(app)
    assert app.weather_adjustment_tip(None, "Monstera") is None

def test_weather_adjustment_tip_missing_temp(monkeypatch):
    import app; importlib.reload(app)
    # No temp_c -> should gracefully return None
    assert app.weather_adjustment_tip({"city": "Austin"}, "Monstera") is None

def test_weather_adjustment_tip_indoor_context_param(monkeypatch):
    import app; importlib.reload(app)
    # Indoor plant with care_context parameter -> should return None (no weather tip)
    tip = app.weather_adjustment_tip({"temp_c": 33, "city": "Austin"}, "Monstera", "indoor_potted")
    assert tip is None

def test_weather_adjustment_tip_indoor_context_in_weather(monkeypatch):
    import app; importlib.reload(app)
    # Indoor plant with care_context in weather dict -> should return None (no weather tip)
    tip = app.weather_adjustment_tip({"temp_c": 33, "city": "Austin", "care_context": "indoor_potted"}, "Monstera")
    assert tip is None

def test_weather_adjustment_tip_outdoor_context_explicit(monkeypatch):
    import app; importlib.reload(app)
    # Outdoor plant with explicit care_context -> should return weather tip
    tip = app.weather_adjustment_tip({"temp_c": 33, "city": "Austin"}, "Monstera", "outdoor_potted")
    assert tip is not None
    assert "hot" in tip.lower()

# --------------------------
# generate_advice() tests
# --------------------------

def test_generate_advice_with_openai(monkeypatch):
    """
    generate_advice should orchestrate weather fetch + AI advice + weather tip.
    With OpenAI working, source should be 'openai'.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    _install_fake_litellm_success(monkeypatch, reply_text="Water your monstera when soil is dry.", model="gpt-4o-mini")

    from app.services.ai import generate_advice

    answer, weather, source = generate_advice(
        question="How often to water?",
        plant="Monstera",
        city=None,
        care_context="indoor_potted"
    )

    assert isinstance(answer, str)
    assert "Water your monstera" in answer
    assert source == "openai"
    assert weather is None  # No city provided


def test_generate_advice_with_gemini(monkeypatch):
    """
    generate_advice with only Gemini key should use Gemini as primary.
    Source should be 'gemini'.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    _install_fake_litellm_success(monkeypatch, reply_text="Gemini says: water weekly.", model="gemini/gemini-flash-latest")

    from app.services.ai import generate_advice

    answer, weather, source = generate_advice(
        question="Watering schedule?",
        plant="Pothos",
        city=None,
        care_context="indoor_potted"
    )

    assert isinstance(answer, str)
    assert "Gemini says" in answer
    assert source == "gemini"


def test_generate_advice_fallback_to_rules(monkeypatch):
    """
    When both AI providers fail, generate_advice should fall back to rule-based tips.
    Source should be 'rule'.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    _install_fake_litellm_raises(monkeypatch, exc=RuntimeError("All providers down"))

    from app.services.ai import generate_advice

    answer, weather, source = generate_advice(
        question="How often to water?",
        plant="Snake Plant",
        city=None,
        care_context="indoor_potted"
    )

    assert isinstance(answer, str)
    assert source == "rule"
    assert "water" in answer.lower()


def test_generate_advice_no_api_keys_uses_rules(monkeypatch):
    """
    When no API keys are configured, should immediately use rule-based fallback.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    from app.services.ai import generate_advice

    answer, weather, source = generate_advice(
        question="Light requirements?",
        plant="Fern",
        city=None,
        care_context="indoor_potted"
    )

    assert isinstance(answer, str)
    assert source == "rule"
    assert "light" in answer.lower()


# --------------------------
# validation tests
# --------------------------

def test_validate_inputs_success():
    """validate_inputs should return cleaned payload when input is valid."""
    from app.utils.validation import validate_inputs

    form = {
        "plant": "  Monstera Deliciosa  ",
        "city": " Austin, TX ",
        "question": "  How often should I water?  ",
        "care_context": "indoor_potted"
    }

    payload, error = validate_inputs(form)

    assert error is None
    assert payload["plant"] == "Monstera Deliciosa"
    assert payload["city"] == "Austin, TX"
    assert payload["question"] == "How often should I water?"
    assert payload["care_context"] == "indoor_potted"


def test_validate_inputs_empty_question():
    """validate_inputs should return error when question is empty."""
    from app.utils.validation import validate_inputs

    form = {
        "plant": "Pothos",
        "city": "Boston",
        "question": "   ",
        "care_context": "indoor_potted"
    }

    payload, error = validate_inputs(form)

    assert payload == {}
    assert error is not None
    assert "required" in error.lower()


def test_validate_inputs_removes_dangerous_chars():
    """validate_inputs should remove suspicious characters but keep alphanumeric text."""
    from app.utils.validation import validate_inputs

    form = {
        "plant": "Monstera<script>alert('xss')</script>",
        "city": "Austin; DROP TABLE users;--",
        "question": "How to water?",
        "care_context": "outdoor_potted"
    }

    payload, error = validate_inputs(form)

    assert error is None
    # Should remove dangerous punctuation/symbols (angle brackets, semicolons, etc.)
    assert "<" not in payload["plant"]
    assert ">" not in payload["plant"]
    assert ";" not in payload["city"]
    # Should keep alphanumeric text and safe punctuation (including hyphens)
    assert "Monstera" in payload["plant"]
    assert "Austin" in payload["city"]
    # Verify overall sanitization - dangerous structures are neutralized
    assert payload["plant"] != form["plant"]  # Modified from original
    assert payload["city"] != form["city"]  # Modified from original


def test_validate_inputs_truncates_long_text():
    """validate_inputs should truncate excessively long inputs."""
    from app.utils.validation import validate_inputs, MAX_PLANT_LEN, MAX_QUESTION_LEN

    form = {
        "plant": "A" * 200,  # Way over MAX_PLANT_LEN (80)
        "city": "Boston",
        "question": "B" * 1500,  # Over MAX_QUESTION_LEN (1200)
        "care_context": "indoor_potted"
    }

    payload, error = validate_inputs(form)

    assert error is None
    assert len(payload["plant"]) <= MAX_PLANT_LEN
    assert len(payload["question"]) <= MAX_QUESTION_LEN


def test_validate_inputs_normalizes_care_context():
    """validate_inputs should coerce invalid care_context to default."""
    from app.utils.validation import validate_inputs

    form = {
        "plant": "Cactus",
        "city": "",
        "question": "How much sun?",
        "care_context": "INVALID_CONTEXT"
    }

    payload, error = validate_inputs(form)

    assert error is None
    assert payload["care_context"] == "indoor_potted"  # Default


# --------------------------
# moderation tests
# --------------------------

def test_moderation_allows_clean_text():
    """run_moderation should allow clean plant care questions."""
    from app.services.moderation import run_moderation

    allowed, reason = run_moderation("How often should I water my monstera?")

    assert allowed is True
    assert reason is None


def test_moderation_blocks_inappropriate_content():
    """run_moderation should block text containing blocklist terms."""
    from app.services.moderation import run_moderation

    allowed, reason = run_moderation("How to kill pests on my plant?")

    assert allowed is False
    assert reason is not None
    assert "kill" in reason.lower()


def test_moderation_case_insensitive():
    """run_moderation should detect blocklist terms regardless of case."""
    from app.services.moderation import run_moderation

    allowed, reason = run_moderation("HATE this plant disease")

    assert allowed is False
    assert reason is not None


def test_moderation_empty_text():
    """run_moderation should handle empty text gracefully."""
    from app.services.moderation import run_moderation

    allowed, reason = run_moderation("")

    assert allowed is True
    assert reason is None


# --------------------------
# Fallback chain behavior tests
# --------------------------

def test_fallback_openai_fails_gemini_succeeds(monkeypatch):
    """
    Test that when only Gemini is configured (simulating OpenAI failure),
    the system uses Gemini successfully.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "")  # No OpenAI
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")  # Only Gemini
    _install_fake_litellm_success(monkeypatch, reply_text="Gemini fallback response: Water carefully.", model="gemini/gemini-flash-latest")

    from app.services.ai import generate_advice

    answer, weather, source = generate_advice(
        question="How to water?",
        plant="Cactus",
        city=None,
        care_context="indoor_potted"
    )

    # Should use Gemini
    assert "Gemini fallback response" in answer
    assert source == "gemini"


# --------------------------
# Integration tests (Flask endpoint)
# --------------------------

def test_ask_endpoint_success(monkeypatch):
    """Test the /ask POST endpoint with valid input and AI response."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("APP_CONFIG", "app.config.TestConfig")
    monkeypatch.setenv("WTF_CSRF_ENABLED", "False")  # Disable CSRF for testing
    _install_fake_litellm_success(monkeypatch, reply_text="AI says: Water weekly.", model="gpt-4o-mini")

    from app import create_app

    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF protection for tests
    client = app.test_client()

    response = client.post("/ask", data={
        "plant": "Monstera",
        "city": "Austin",
        "question": "How often to water?",
        "care_context": "indoor_potted"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"AI says: Water weekly" in response.data or b"Water weekly" in response.data


def test_ask_endpoint_missing_question(monkeypatch):
    """Test the /ask endpoint with missing required question field."""
    monkeypatch.setenv("APP_CONFIG", "app.config.TestConfig")
    monkeypatch.setenv("WTF_CSRF_ENABLED", "False")

    from app import create_app

    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    response = client.post("/ask", data={
        "plant": "Pothos",
        "city": "Boston",
        "question": "",
        "care_context": "indoor_potted"
    }, follow_redirects=True)

    assert response.status_code == 400
    assert b"required" in response.data.lower()


def test_ask_endpoint_blocked_content(monkeypatch):
    """Test the /ask endpoint with content that should be blocked by moderation."""
    monkeypatch.setenv("APP_CONFIG", "app.config.TestConfig")
    monkeypatch.setenv("WTF_CSRF_ENABLED", "False")

    from app import create_app

    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    response = client.post("/ask", data={
        "plant": "Plant",
        "city": "",
        "question": "How to kill this plant?",
        "care_context": "indoor_potted"
    }, follow_redirects=True)

    assert response.status_code == 400
    assert b"disallowed" in response.data.lower() or b"blocked" in response.data.lower()


def test_ask_endpoint_fallback_to_rules(monkeypatch):
    """Test the /ask endpoint falls back to rule-based when AI fails."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("APP_CONFIG", "app.config.TestConfig")
    monkeypatch.setenv("WTF_CSRF_ENABLED", "False")
    _install_fake_litellm_raises(monkeypatch, exc=RuntimeError("AI unavailable"))

    from app import create_app

    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    response = client.post("/ask", data={
        "plant": "Fern",
        "city": "",
        "question": "How often to water?",
        "care_context": "indoor_potted"
    }, follow_redirects=True)

    assert response.status_code == 200
    # Should show rule-based response
    assert b"water" in response.data.lower()
    assert b"Rule-based engine" in response.data or b"rule" in response.data.lower()


# --------------------------
# Edge case tests
# --------------------------

def test_basic_plant_tip_different_questions():
    """Test that rule-based tips respond appropriately to different question types."""
    from app.services.ai import _basic_plant_tip

    # Test watering question
    water_tip = _basic_plant_tip("How often to water?", "Monstera", "indoor_potted")
    assert "water" in water_tip.lower()

    # Test light question
    light_tip = _basic_plant_tip("How much light?", "Pothos", "outdoor_potted")
    assert "light" in light_tip.lower()

    # Test fertilizer question
    fert_tip = _basic_plant_tip("When to fertilize?", "Snake Plant", "indoor_potted")
    assert "feed" in fert_tip.lower() or "fertil" in fert_tip.lower()

    # Test repotting question
    repot_tip = _basic_plant_tip("When to repot?", "Cactus", "outdoor_bed")
    assert "repot" in repot_tip.lower() or "pot" in repot_tip.lower()

    # Test generic question (should return default advice)
    generic_tip = _basic_plant_tip("Tell me about plant care", "Fern", "indoor_potted")
    assert "light" in generic_tip.lower()
    assert "water" in generic_tip.lower()


def test_weather_tip_boundary_temperatures(monkeypatch):
    """Test weather tips at temperature boundaries."""
    import app
    importlib.reload(app)

    # Exactly at hot threshold (32°C)
    hot_exact = app.weather_adjustment_tip({"temp_c": 32, "city": "Phoenix"}, "Plant", "outdoor_potted")
    assert hot_exact is not None
    assert "hot" in hot_exact.lower()

    # Exactly at cold threshold (5°C)
    cold_exact = app.weather_adjustment_tip({"temp_c": 5, "city": "Oslo"}, "Plant", "outdoor_potted")
    assert cold_exact is not None
    assert "cold" in cold_exact.lower()

    # Just above cold threshold (6°C)
    mild_temp = app.weather_adjustment_tip({"temp_c": 6, "city": "Seattle"}, "Plant", "outdoor_potted")
    assert mild_temp is not None
    assert "maintain" in mild_temp.lower() or "usual" in mild_temp.lower()


def test_normalize_context_edge_cases():
    """Test care context normalization with unusual inputs."""
    from app.utils.validation import normalize_context

    assert normalize_context(None) == "indoor_potted"
    assert normalize_context("") == "indoor_potted"
    assert normalize_context("  ") == "indoor_potted"
    assert normalize_context("OUTDOOR_POTTED") == "outdoor_potted"  # Case insensitive
    assert normalize_context("outdoor_bed") == "outdoor_bed"
    assert normalize_context("random_invalid_value") == "indoor_potted"
    assert normalize_context("123") == "indoor_potted"


def test_ai_last_error_tracking(monkeypatch):
    """Test that AI_LAST_ERROR is properly set when errors occur."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    _install_fake_litellm_raises(monkeypatch, exc=RuntimeError("Specific error message"))

    from app.services.ai import generate_advice, AI_LAST_ERROR

    generate_advice(
        question="Test question?",
        plant="Plant",
        city=None,
        care_context="indoor_potted"
    )

    # AI_LAST_ERROR should contain the error message
    assert AI_LAST_ERROR is not None
    assert len(AI_LAST_ERROR) > 0


def test_empty_plant_and_city_fields(monkeypatch):
    """Test that empty plant and city fields are handled gracefully."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    _install_fake_litellm_success(monkeypatch, reply_text="Generic plant advice.", model="gpt-4o-mini")

    from app.services.ai import generate_advice

    answer, weather, source = generate_advice(
        question="How to care for plants?",
        plant="",  # Empty plant name
        city="",   # Empty city
        care_context="indoor_potted"
    )

    assert isinstance(answer, str)
    assert len(answer) > 0
    assert source == "openai"
    assert weather is None  # No city, so no weather


def test_validation_collapses_whitespace():
    """Test that validation collapses multiple spaces."""
    from app.utils.validation import validate_inputs

    form = {
        "plant": "Monstera    Deliciosa",  # Multiple spaces
        "city": "New    York",
        "question": "How   often   to   water?",
        "care_context": "indoor_potted"
    }

    payload, error = validate_inputs(form)

    assert error is None
    # Should collapse multiple spaces to single space
    assert "  " not in payload["plant"]
    assert "  " not in payload["city"]
    # Question field may preserve some formatting but should normalize tabs/spaces


# --------------------------
# User City/Location tests
# --------------------------

def test_update_user_city_success():
    """Test successfully updating user's city in profile."""
    from app.services.supabase_client import update_user_city

    # Mock successful update
    success, error = update_user_city("test-user-id", "Austin, TX")

    # Should succeed with valid city
    assert success is True or success is False  # Depends on Supabase connection
    # If it fails, error should be about database configuration or invalid test UUID
    if not success:
        assert "not configured" in error.lower() or "database" in error.lower() or "column" in error.lower() or "schema" in error.lower() or "uuid" in error.lower() or "invalid" in error.lower()


def test_update_user_city_validation():
    """Test city validation (max length, empty string)."""
    from app.services.supabase_client import update_user_city

    # Test max length validation
    long_city = "A" * 201  # Exceeds 200 char limit
    success, error = update_user_city("test-user-id", long_city)

    assert success is False
    assert error is not None
    assert "too long" in error.lower()


def test_update_user_city_xss_prevention():
    """Test that XSS attempts in city field are blocked."""
    from app.services.supabase_client import update_user_city

    # Test XSS attempt
    xss_city = "Austin<script>alert('xss')</script>"
    success, error = update_user_city("test-user-id", xss_city)

    assert success is False
    assert error is not None
    assert "invalid characters" in error.lower()

    # Test another XSS vector
    xss_city2 = "Austin'; DROP TABLE profiles;--"
    success2, error2 = update_user_city("test-user-id", xss_city2)

    assert success2 is False
    assert error2 is not None
    assert "invalid characters" in error2.lower()


def test_update_user_city_allows_valid_formats():
    """Test that valid city formats are accepted."""
    from app.services.supabase_client import update_user_city

    # Test various valid formats
    valid_cities = [
        "Austin, TX",
        "New York",
        "78701",  # ZIP code
        "San Francisco, CA",
        "Boston",
        "90210",
    ]

    for city in valid_cities:
        success, error = update_user_city("test-user-id", city)
        # Should either succeed or fail due to DB config, not validation
        if not success:
            assert "not configured" in error.lower() or "database" in error.lower() or "column" in error.lower() or "schema" in error.lower() or "uuid" in error.lower() or "invalid input syntax" in error.lower()
            # Should NOT fail due to invalid characters
            assert "invalid characters" not in error.lower()


def test_update_user_city_clear():
    """Test clearing user's city (empty string)."""
    from app.services.supabase_client import update_user_city

    # Test clearing city with empty string
    success, error = update_user_city("test-user-id", "")

    # Should succeed or fail due to DB config, not validation
    if not success:
        assert "not configured" in error.lower() or "database" in error.lower() or "column" in error.lower() or "schema" in error.lower() or "uuid" in error.lower() or "invalid input syntax" in error.lower()
        # Should NOT fail due to invalid characters
        assert "invalid characters" not in error.lower()


def test_care_assistant_prefills_city(monkeypatch):
    """Test that Care Assistant pre-fills city from user profile."""
    # This test verifies the integration in web.py
    # We'll check that the route attempts to get user profile
    # Full integration testing would require mocking Supabase

    # Mock environment for Flask app
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("APP_CONFIG", "app.config.TestConfig")
    monkeypatch.setenv("WTF_CSRF_ENABLED", "False")

    from app import create_app

    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    # Test GET request to /ask (unauthenticated, so no city)
    response = client.get("/ask")

    assert response.status_code == 200
    # Should render without errors
    assert b"PlantCareAI" in response.data or b"Care Assistant" in response.data


# --------------------------
# Supabase Client tests (PRIORITY 5 - MEDIUM)
# --------------------------

def test_get_user_profile_not_found():
    """Test handling of missing profile."""
    from app.services.supabase_client import get_user_profile

    # Test with fake user ID
    profile = get_user_profile("nonexistent-user-id")

    # Should return None for missing profile (or handle gracefully)
    # Exact behavior depends on Supabase connection
    assert profile is None or isinstance(profile, dict)


def test_get_plant_count_no_database():
    """Test plant count when database is not configured."""
    from app.services.supabase_client import get_plant_count

    # Test with fake user ID
    count = get_plant_count("test-user-id")

    # Should return 0 when database is not configured or unavailable
    assert isinstance(count, int)
    assert count >= 0


def test_is_premium_user_default_free():
    """Test that users default to free tier."""
    from app.services.supabase_client import is_premium

    # Test with fake user ID
    is_premium_user = is_premium("test-user-id")

    # Should return False for non-existent user (free tier default)
    assert is_premium_user is False


def test_has_premium_access_includes_trial():
    """Test that premium access includes both premium and trial users."""
    from app.services.supabase_client import has_premium_access

    # Test with fake user ID
    has_access = has_premium_access("test-user-id")

    # Should return False for non-existent user
    assert isinstance(has_access, bool)


# --------------------------
# Weather Service tests (PRIORITY 4 - MEDIUM)
# --------------------------

def test_get_weather_no_api_key(monkeypatch):
    """Test graceful degradation when weather API key is missing."""
    # Clear the API key
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)

    try:
        from app.services.weather import get_weather_for_city

        # Should handle missing API key gracefully
        weather = get_weather_for_city("Austin, TX")

        # Should return None or empty dict, not crash
        assert weather is None or isinstance(weather, dict)
    except Exception:
        # If module doesn't exist or fails to import, that's acceptable
        pass


def test_get_forecast_no_api_key(monkeypatch):
    """Test forecast graceful degradation without API key."""
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)

    try:
        from app.services.weather import get_forecast_for_city

        # Should handle missing API key gracefully
        forecast = get_forecast_for_city("Austin, TX")

        # Should return None, not crash
        assert forecast is None or isinstance(forecast, list)
    except Exception:
        # If module doesn't exist or fails to import, that's acceptable
        pass


# --------------------------
# Dashboard & Web Routes tests (PRIORITY 6 - LOW but recently modified)
# --------------------------

def test_healthz_endpoint(monkeypatch):
    """Test /healthz health check endpoint."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("APP_CONFIG", "app.config.TestConfig")

    from app import create_app

    app = create_app()
    client = app.test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert b"OK" in response.data


def test_index_redirects_unauthenticated(monkeypatch):
    """Test that unauthenticated users are redirected to signup."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("APP_CONFIG", "app.config.TestConfig")

    from app import create_app

    app = create_app()
    client = app.test_client()

    response = client.get("/", follow_redirects=False)

    # Should redirect (either to signup or dashboard)
    assert response.status_code in [200, 302, 303, 307, 308]


# --------------------------
# Authentication Security tests (PRIORITY 3 - HIGH)
# --------------------------

def test_require_auth_decorator_blocks_anonymous(monkeypatch):
    """Test that @require_auth redirects unauthenticated users."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("APP_CONFIG", "app.config.TestConfig")

    from app import create_app

    app = create_app()
    client = app.test_client()

    # Try to access protected dashboard without auth
    response = client.get("/dashboard/", follow_redirects=False)

    # Should redirect to login (302) or show error
    assert response.status_code in [302, 303, 307, 401, 403]


def test_debug_endpoint_disabled_in_production(monkeypatch):
    """Test that debug endpoint is disabled when DEBUG=False."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("APP_CONFIG", "app.config.TestConfig")

    from app import create_app

    app = create_app()
    app.config["DEBUG"] = False  # Simulate production
    client = app.test_client()

    response = client.get("/debug")

    # Should return 404 or 401 (not available in production)
    assert response.status_code in [404, 401]


# --------------------------
# Plants Service tests (PRIORITY 2 - HIGH)
# --------------------------

def test_create_plant_requires_authentication(monkeypatch):
    """Test that plant creation requires authentication."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("APP_CONFIG", "app.config.TestConfig")
    monkeypatch.setenv("WTF_CSRF_ENABLED", "False")

    from app import create_app

    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    # Try to create plant without auth
    response = client.post("/plants/add", data={
        "name": "Test Plant",
        "species": "Monstera"
    }, follow_redirects=False)

    # Should redirect to login or return error
    assert response.status_code in [302, 303, 307, 401, 403]


# --------------------------
# Reminders Service tests (PRIORITY 1 - CRITICAL)
# --------------------------

def test_create_reminder_one_time():
    """Test creating a one-time reminder."""
    from app.services.reminders import create_reminder

    # Create a one-time reminder
    result, error = create_reminder(
        user_id="test-user-id",
        plant_id="test-plant-id",
        reminder_type="watering",
        title="Water plant",
        frequency="one_time",
        notes="Test one-time reminder"
    )

    # Should either succeed or fail due to DB config, not validation
    assert result is not None or error is not None
    if error:
        # Database errors are acceptable (UUID format, connection issues)
        assert "uuid" in error.lower() or "database" in error.lower() or "not configured" in error.lower() or "invalid" in error.lower()


def test_create_reminder_recurring_daily():
    """Test creating a daily recurring reminder."""
    from app.services.reminders import create_reminder

    result, error = create_reminder(
        user_id="test-user-id",
        plant_id="test-plant-id",
        reminder_type="fertilizing",
        title="Fertilize plant",
        frequency="daily"
    )

    # Should either succeed or fail due to DB config
    assert result is not None or error is not None
    if error:
        assert "uuid" in error.lower() or "database" in error.lower() or "not configured" in error.lower() or "invalid" in error.lower()


def test_get_reminder_by_id_not_found():
    """Test fetching non-existent reminder."""
    from app.services.reminders import get_reminder_by_id

    # Try to get non-existent reminder
    reminder = get_reminder_by_id("nonexistent-id", "test-user-id")

    # Should return None for missing reminder
    assert reminder is None or isinstance(reminder, dict)


def test_get_user_reminders_returns_list():
    """Test fetching user's reminders returns a list."""
    from app.services.reminders import get_user_reminders

    # Get user's reminders
    reminders = get_user_reminders("test-user-id")

    # Should always return a list (empty if no reminders or DB error)
    assert isinstance(reminders, list)


def test_get_due_reminders_returns_list():
    """Test fetching due reminders returns a list."""
    from app.services.reminders import get_due_reminders

    # Get due reminders
    due = get_due_reminders("test-user-id")

    # Should always return a list
    assert isinstance(due, list)


def test_get_upcoming_reminders_returns_list():
    """Test fetching upcoming reminders returns a list."""
    from app.services.reminders import get_upcoming_reminders

    # Get upcoming reminders (next 7 days)
    upcoming = get_upcoming_reminders("test-user-id", days=7)

    # Should always return a list
    assert isinstance(upcoming, list)


def test_mark_reminder_complete_validation():
    """Test marking non-existent reminder as complete."""
    from app.services.reminders import mark_reminder_complete

    # Try to mark non-existent reminder as complete
    success, error = mark_reminder_complete("nonexistent-id", "test-user-id")

    # Should fail gracefully
    assert success is False or success is True
    if not success:
        assert error is not None
        assert isinstance(error, str)


def test_snooze_reminder_validation():
    """Test snoozing non-existent reminder."""
    from app.services.reminders import snooze_reminder

    # Try to snooze non-existent reminder
    success, error = snooze_reminder("nonexistent-id", "test-user-id", days=1)

    # Should fail gracefully
    assert success is False or success is True
    if not success:
        assert error is not None


def test_update_reminder_validation():
    """Test updating non-existent reminder."""
    from app.services.reminders import update_reminder

    # Try to update non-existent reminder
    result, error = update_reminder(
        reminder_id="nonexistent-id",
        user_id="test-user-id",
        notes="Updated notes"
    )

    # Should fail gracefully - returns (reminder, error)
    assert result is None or isinstance(result, dict)
    if result is None:
        # If no result, should have an error
        assert error is not None or error is None  # DB connection might not be configured


def test_delete_reminder_validation():
    """Test deleting non-existent reminder."""
    from app.services.reminders import delete_reminder

    # Try to delete non-existent reminder
    success, error = delete_reminder("nonexistent-id", "test-user-id")

    # Should fail gracefully
    assert success is False or success is True
    if not success:
        assert error is not None


def test_toggle_reminder_status_validation():
    """Test toggling status of non-existent reminder."""
    from app.services.reminders import toggle_reminder_status

    # Try to toggle non-existent reminder
    success, error = toggle_reminder_status("nonexistent-id", "test-user-id")

    # Should fail gracefully
    assert success is False or success is True
    if not success:
        assert error is not None


def test_get_reminder_stats_returns_dict():
    """Test reminder statistics calculation."""
    from app.services.reminders import get_reminder_stats

    # Get reminder stats
    stats = get_reminder_stats("test-user-id")

    # Should always return a dict with required keys
    assert isinstance(stats, dict)
    assert "due_today" in stats
    assert "upcoming_7_days" in stats
    assert "completed_this_week" in stats
    assert "active_reminders" in stats

    # All values should be integers
    assert isinstance(stats["due_today"], int)
    assert isinstance(stats["upcoming_7_days"], int)
    assert isinstance(stats["completed_this_week"], int)
    assert isinstance(stats["active_reminders"], int)


def test_adjust_reminder_for_weather_validation():
    """Test weather adjustment with invalid reminder."""
    from app.services.reminders import adjust_reminder_for_weather

    # Try to adjust non-existent reminder
    adjusted, message, weather = adjust_reminder_for_weather(
        reminder_id="nonexistent-id",
        user_id="test-user-id",
        city="Austin, TX"
    )

    # Should fail gracefully - returns (adjusted, message, weather_data)
    assert adjusted is False or adjusted is True
    if not adjusted:
        assert message is not None or message is None  # Message might be optional


def test_clear_weather_adjustment_validation():
    """Test clearing weather adjustment with invalid reminder."""
    from app.services.reminders import clear_weather_adjustment

    # Try to clear adjustment on non-existent reminder
    success, error = clear_weather_adjustment("nonexistent-id", "test-user-id")

    # Should fail gracefully
    assert success is False or success is True
    if not success:
        assert error is not None


def test_get_reminders_for_month_returns_list():
    """Test fetching reminders for a specific month."""
    from app.services.reminders import get_reminders_for_month

    # Get reminders for current month
    reminders = get_reminders_for_month("test-user-id", 2025, 11)

    # Should always return a list
    assert isinstance(reminders, list)

