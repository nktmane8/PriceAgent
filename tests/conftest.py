import os
import sys
import tempfile

# Settings are read at import time, so set them before importing the app.
os.environ.update(DATABASE_PATH=os.path.join(tempfile.mkdtemp(), "boot.db"), API_KEYS="testkey",
                  ADMIN_KEY="adm", PUBLIC_URL="http://127.0.0.1:8000")
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


@pytest.fixture
def calls():
    return []


@pytest.fixture(scope="session")
def _session_client():
    # The MCP session manager can start only once per process, so share one client for the whole run.
    with TestClient(main.app, base_url="http://127.0.0.1:8000") as c:
        yield c


@pytest.fixture
def client(_session_client, tmp_path, monkeypatch, calls):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))  # fresh database per test
    db.init()

    def fake(product, country, city, sites):  # no network: stand-in for the real agent
        calls.append(product)
        return agent.clean(RESULT), {"input_tokens": 10, "output_tokens": 5, "searches": 2}
    monkeypatch.setattr(agent, "run_agent", fake)
    return _session_client
