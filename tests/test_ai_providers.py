import agent
import config


def test_gemini_provider_is_supported(monkeypatch):
    calls = []

    monkeypatch.setattr(config, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(agent, "_provider_configured", lambda provider: provider == "gemini")
    monkeypatch.setattr(
        agent,
        "_converse_gemini",
        lambda system, prompt, max_tokens: (
            '{"ok": true}',
            {"input_tokens": 10, "output_tokens": 5, "searches": 2},
        ),
    )

    text, usage = agent._converse("system", "prompt", 1, 100)

    assert text == '{"ok": true}'
    assert usage["searches"] == 2


def test_auto_provider_falls_back_from_gemini_to_openai(monkeypatch):
    calls = []

    monkeypatch.setattr(config, "AI_PROVIDER", "auto")
    monkeypatch.setattr(config, "AI_MAX_RETRIES", 0)
    monkeypatch.setattr(agent, "_provider_configured", lambda provider: provider in {"gemini", "openai"})

    def gemini(*args):
        calls.append("gemini")
        raise RuntimeError("503 unavailable")

    def openai(*args):
        calls.append("openai")
        return '{"ok": true}', {"input_tokens": 3, "output_tokens": 2, "searches": 1}

    monkeypatch.setattr(agent, "_converse_gemini", gemini)
    monkeypatch.setattr(agent, "_converse_openai", openai)

    text, usage = agent._converse("system", "prompt", 1, 100)

    assert calls == ["gemini", "openai"]
    assert text == '{"ok": true}'
    assert usage["input_tokens"] == 3


def test_provider_order_can_explicitly_select_both(monkeypatch):
    monkeypatch.setattr(config, "AI_PROVIDER", "gemini,openai")
    assert agent._provider_order() == ["gemini", "openai"]

def test_auto_provider_order_includes_all_fallbacks(monkeypatch):
    monkeypatch.setattr(config, "AI_PROVIDER", "auto")
    assert agent._provider_order() == ["groq", "gemini", "huggingface", "ollama", "openai"]


def test_auto_skips_unconfigured_providers(monkeypatch):
    calls = []
    monkeypatch.setattr(config, "AI_PROVIDER", "auto")
    monkeypatch.setattr(config, "AI_MAX_RETRIES", 0)
    monkeypatch.setattr(agent, "_provider_configured", lambda provider: provider in {"ollama"})
    monkeypatch.setattr(agent, "_converse_ollama", lambda *args: (calls.append("ollama") or '{"ok": true}', {"input_tokens": 1, "output_tokens": 1, "searches": 0}))
    text, usage = agent._converse("system", "prompt", 1, 100)
    assert calls == ["ollama"]
    assert text == '{"ok": true}'
