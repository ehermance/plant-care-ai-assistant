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

def _install_fake_openai_success(monkeypatch, reply_text="• Tip 1\n• Tip 2"):
    """
    Inject a fake 'openai' module into sys.modules so that
    'from openai import OpenAI' works inside app.ai_advice().
    This fake returns a deterministic response.
    """
    class FakeMessage:
        def __init__(self, content): self.content = content

    class FakeChoice:
        def __init__(self, content): self.message = FakeMessage(content)

    class FakeResp:
        def __init__(self, content): self.choices = [FakeChoice(content)]

    class FakeChatCompletions:
        def create(self, **kwargs):
            # You can assert model/temperature/etc here if desired.
            return FakeResp(reply_text)

    class FakeChat:
        def __init__(self): self.completions = FakeChatCompletions()

    class FakeOpenAI:
        def __init__(self, api_key=None): self.chat = FakeChat()

    fake_mod = types.SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_mod)


def _install_fake_openai_raises(monkeypatch, exc=RuntimeError("boom")):
    """Fake OpenAI client that raises when .create() is called."""
    class FakeChatCompletions:
        def create(self, **kwargs): raise exc
    class FakeChat:
        def __init__(self): self.completions = FakeChatCompletions()
    class FakeOpenAI:
        def __init__(self, api_key=None): self.chat = FakeChat()
    fake_mod = types.SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_mod)


def test_ai_advice_no_key(monkeypatch):
    """
    When OPENAI_API_KEY is empty/missing, ai_advice should return None and
    should NOT need the openai module at all.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "")
    import app
    importlib.reload(app)

    out = app.ai_advice("How often to water?", "Monstera", weather=None)
    assert out is None


def test_ai_advice_success(monkeypatch):
    """
    With a key present and a fake OpenAI that returns a canned response,
    ai_advice should return that text (stripped).
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    _install_fake_openai_success(monkeypatch, reply_text="• AI: water in the morning.\n• AI: bright-indirect light.")
    import app
    importlib.reload(app)

    txt = app.ai_advice("Watering schedule?", "Pothos", weather={"city":"Austin","temp_c":31})
    assert isinstance(txt, str)
    assert "AI: water in the morning" in txt
    assert "AI: bright-indirect light" in txt


def test_ai_advice_exception(monkeypatch):
    """
    If the OpenAI client throws, ai_advice should swallow and return None.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    _install_fake_openai_raises(monkeypatch, exc=RuntimeError("rate limit"))
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

