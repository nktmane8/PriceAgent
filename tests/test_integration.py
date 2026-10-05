import pytest
import openai

import agent
import main
import io
import json
import urllib.request


class FakeResponse:
    status = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({
            "address": {
                "country": "India",
                "city": "Pune",
            }
        }).encode()

    def __iter__(self):
        return iter(())


def test_locate_integration_contract(_session_client, monkeypatch):
    def fake_urlopen(request, timeout):
        assert request.full_url.startswith("https://nominatim.openstreetmap.org/reverse?")
        assert request.headers["User-agent"].startswith("price-agent/1.0")
        assert timeout == 5
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    response = _session_client.get("/api/locate", params={"lat": 18.62, "lon": 73.73})

    assert response.status_code == 200
    assert response.json() == {"country": "India", "city": "Pune"}


def test_compare_api_returns_200_for_completed_job(client, monkeypatch):
    monkeypatch.setattr(main.jobs, "wait", lambda jid, timeout: {
        "id": jid,
        "status": "done",
        "result": {"product": "Phone X"},
        "source": "agent",
    })

    response = client.post(
        "/api/v1/compare",
        headers={"X-API-Key": "testkey"},
        json={"product": "Phone X", "country": "India", "city": "Pune"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_compare_api_does_not_return_200_for_failed_job(client, monkeypatch):
    monkeypatch.setattr(main.jobs, "wait", lambda jid, timeout: {
        "id": jid,
        "status": "error",
        "error": "The AI service is busy. Try again shortly.",
    })

    response = client.post(
        "/api/v1/compare",
        headers={"X-API-Key": "testkey"},
        json={"product": "Phone X", "country": "India", "city": "Pune"},
    )

    assert response.status_code == 502
    assert response.json()["status"] == "error"



def test_ai_rate_limit_is_classified_without_network(monkeypatch):
    class FakeResponse:
        headers = {"x-request-id": "req-test"}
        def json(self):
            return {"error": {"type": "insufficient_quota", "code": "insufficient_quota", "message": "quota exceeded"}}

    class FakeResponses:
        def create(self, **kwargs):
            error = openai.RateLimitError("rate limited", response=FakeResponse(), body=None)
            raise error

    class FakeClient:
        responses = FakeResponses()

    monkeypatch.setattr(agent, "OpenAI", lambda **kwargs: FakeClient())

    monkeypatch.setattr(agent.config, "AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with pytest.raises(agent.AgentError, match="unavailable or over quota"):
        agent._converse("system", "prompt", 1, 100)


def test_ai_rate_limit_retries_once_then_succeeds(monkeypatch):
    attempts = {"count": 0}

    class FakeResponse:
        headers = {"x-request-id": "req-retry"}

        def json(self):
            return {"error": {"type": "rate_limit_error", "code": "rate_limit_exceeded", "message": "slow down"}}

    class FakeUsage:
        input_tokens = 11
        output_tokens = 7

    class FakeOutput:
        type = "message"

    class FakeResult:
        output = [FakeOutput()]
        output_text = '{"ok": true}'
        usage = FakeUsage()

    class FakeResponses:
        def create(self, **kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise openai.RateLimitError("rate limited", response=FakeResponse(), body=None)
            return FakeResult()

    class FakeClient:
        responses = FakeResponses()

    monkeypatch.setattr(agent, "OpenAI", lambda **kwargs: FakeClient())
    monkeypatch.setattr(agent.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(agent.config, "AI_MAX_RETRIES", 1)
    monkeypatch.setattr(agent.config, "AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    text, usage = agent._converse("system", "prompt", 1, 100)

    assert attempts["count"] == 2
    assert text == '{"ok": true}'
    assert usage == {"input_tokens": 11, "output_tokens": 7, "searches": 0}


def test_compare_api_returns_202_while_job_is_running(client, monkeypatch):
    monkeypatch.setattr(main.jobs, "wait", lambda jid, timeout: {
        "id": jid,
        "status": "running",
    })

    response = client.post(
        "/api/v1/compare",
        headers={"X-API-Key": "testkey"},
        json={"product": "Phone X", "country": "India", "city": "Pune"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "running"


def test_job_poll_returns_404_for_unknown_job(client):
    response = client.get(
        "/api/v1/jobs/does-not-exist",
        headers={"X-API-Key": "testkey"},
    )

    assert response.status_code == 404
