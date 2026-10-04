import os
import sys
import tempfile

os.environ.update(APP_ENV="test", DATABASE_PATH=os.path.join(tempfile.mkdtemp(), "boot.db"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi.testclient import TestClient

import app as app_module
from ragapp import config, store


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))
    c = store.connect()
    yield c
    c.close()


@pytest.fixture
def client(conn):
    return TestClient(app_module.app)
