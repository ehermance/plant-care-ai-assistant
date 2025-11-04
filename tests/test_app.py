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

