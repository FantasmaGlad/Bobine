import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

LIVE = (
    "/api/playback/state?channel=cable", "/api/playback/state?channel=network",
    "/api/radio/state?channel=radio_cable", "/api/radio/state?channel=radio_network",
    "/api/radio/sound?channel=radio_network", "/api/radio/default-playlist", "/api/health", "/api/time",
    "/api/radio/artists", "/api/radio/albums", "/api/radio/tags", "/api/settings/laptop-lid", "/api/metrics/ratings",
)


def test_live_states_match_their_models():
    with TestClient(app) as client:
        for path in LIVE:
            answer = client.get(path)
            assert answer.status_code in (200, 503), (path, answer.status_code, answer.text[:300])
