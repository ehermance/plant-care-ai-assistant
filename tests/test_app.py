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
