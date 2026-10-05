import agent
import config


def test_gemini_provider_is_supported(monkeypatch):
    calls = []

    monkeypatch.setattr(config, "AI_PROVIDER", "gemini")
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
