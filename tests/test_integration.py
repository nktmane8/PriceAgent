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

    with pytest.raises(agent.AgentError, match="quota/billing limit"):
        agent._converse("system", "prompt", 1, 100)
