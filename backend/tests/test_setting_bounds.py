import os

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"

import pytest
from fastapi.testclient import TestClient

from app.api.contract import SETTING_BOUNDS
from app.main import app

@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("key", sorted(SETTING_BOUNDS))
def test_values_outside_the_bounds_are_refused_and_edges_accepted(client, key):
    low, high = SETTING_BOUNDS[key]
    original = client.get("/api/settings").json()[key]
    try:
        assert client.put("/api/settings", json={key: high + 1}).status_code == 422
        assert client.put("/api/settings", json={key: -1}).status_code == 422
        for value in (low, high):
            assert client.put("/api/settings", json={key: value}).status_code == 200
            assert client.get("/api/settings").json()[key] == value
    finally:
        client.put("/api/settings", json={key: original})
