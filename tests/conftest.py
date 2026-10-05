import os
import sys
import tempfile

# Settings are read at import time, so set them before importing the app.
os.environ.update(APP_ENV="test", DATABASE_PATH=os.path.join(tempfile.mkdtemp(), "boot.db"),
                  ADMIN_KEY="adm", PUBLIC_URL="http://127.0.0.1:8000",
                  GOOGLE_CLIENT_ID="test-google-client", GOOGLE_CLIENT_SECRET="test-google-secret",
                  JWT_SECRET="test-jwt-secret-which-is-long-enough-for-tests-123456789")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi.testclient import TestClient

import agent
import config
import db
import main

RESULT = {"product": "Phone X", "region": "Pune, India", "currency": "INR",
          "results": [{"site": "a.in", "store_type": "marketplace", "location": "", "price": 100, "effective_price": 90,
                       "offers": ["10 off"], "in_stock": True, "url": "https://a.in/p"},
                      {"site": "b.in", "store_type": "local", "location": "Pune", "price": 95, "effective_price": 95,
                       "offers": [], "in_stock": True, "url": "javascript:alert(1)"}],
          "best_deal": {"site": "a.in", "effective_price": 90, "why": "lowest"}, "notes": ""}
INSIGHTS = {"product": "Phone X", "region": "Pune, India", "currency": "INR", "verdict": "Good for most buyers.",
            "pros": ["solid battery"], "cons": ["slow charging"],
            "user_rating": {"average": 4.2, "count": 1200, "where": "Example Store"},
            "reviews": [{"source": "Example Paper", "source_type": "publication", "reviewer": "A Reviewer",
                         "rating": "4/5", "summary": "Well balanced for the price.", "date": "2026-01-01",
                         "url": "https://example.com/review", "basis": "full_page", "sponsored_or_affiliate": False},
                        {"source": "No Link Blog", "source_type": "publication", "summary": "No source URL.",
                         "url": ""}],
            "alternatives": [{"name": "Phone Y", "why_consider": "Better camera.", "better_at": ["camera"],
                              "trade_off": "Costs more.", "approx_price": 120, "currency": "INR",
                              "url": "javascript:alert(1)"}],
            "notes": ""}


@pytest.fixture
def calls():
    return []


@pytest.fixture(scope="session")
def _session_client():
    # The MCP session manager can start only once per process, so share one client for the whole run.
    # Legacy /api/jobs endpoints are production-OAuth protected. Override only
    # that dependency in tests so the existing lifecycle tests stay focused on jobs.
    main.api.dependency_overrides[main.web_user] = lambda: ("user:test", config.USER_RATE_LIMIT)
    try:
        with TestClient(main.app, base_url="http://127.0.0.1:8000") as c:
            yield c
    finally:
        main.api.dependency_overrides.pop(main.web_user, None)


@pytest.fixture
def client(_session_client, tmp_path, monkeypatch, calls):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))  # fresh database per test
    db.init()

    def fake(product, country, city, sites):  # no network: stand-in for the real agent
        calls.append(product)
        return agent.clean(RESULT), {"input_tokens": 10, "output_tokens": 5, "searches": 2}

    def fake_insights(product, country, city, sites):  # no network: stand-in for the real insights agent
        return agent.clean_insights(INSIGHTS), {"input_tokens": 6, "output_tokens": 4, "searches": 1}

    monkeypatch.setattr(agent, "run_agent", fake)
    monkeypatch.setattr(agent, "run_insights", fake_insights)
    return _session_client
