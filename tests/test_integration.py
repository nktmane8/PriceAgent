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
