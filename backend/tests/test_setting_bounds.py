import os
import re
from pathlib import Path

os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_database.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.contract import SETTING_BOUNDS  # noqa: E402
from app.main import app  # noqa: E402

BOUNDS_TS = Path(__file__).resolve().parents[2] / "frontend/src/lib/settingsBounds.ts"


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


@pytest.mark.skipif(not BOUNDS_TS.exists(), reason="frontend absent")
def test_the_settings_page_uses_the_same_bounds():
    found = {name: (int(low), int(high)) for name, low, high in re.findall(r"(\w+):\s*\{\s*min:\s*(\d+),\s*max:\s*(\d+)", BOUNDS_TS.read_text(encoding="utf-8"))}
    assert found == SETTING_BOUNDS
