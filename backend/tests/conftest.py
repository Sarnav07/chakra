"""Shared pytest fixtures: temporary databases and API test clients."""
import datetime

import pytest
from fastapi.testclient import TestClient

from app.db import get_conn, get_db, init_db
from app.main import app


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    init_db(reset=True, db_path=path)
    return path


@pytest.fixture
def conn(db_path):
    c = get_conn(db_path)
    yield c
    c.close()


def _client_for(path):
    """TestClient whose get_db dependency opens connections to path."""
    def override_get_db():
        c = get_conn(path)
        try:
            yield c
        finally:
            c.close()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def client(db_path):
    yield _client_for(db_path)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_db_path(db_path):
    try:
        from app.seed import run_seed
    except ImportError:
        pytest.skip("seed not available yet")
    run_seed(seed=42, scenario_date=datetime.date(2026, 10, 24), db_path=db_path)
    return db_path


@pytest.fixture
def seeded_client(seeded_db_path):
    yield _client_for(seeded_db_path)
    app.dependency_overrides.clear()
