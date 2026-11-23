import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["BOBINE_DATABASE_URL"] = "sqlite:///data/test_visuals_database.db"
os.environ["BOBINE_VISUALS_DIR"] = "data/test_visuals"
os.environ["BOBINE_VISUALS_WATCH_DIR"] = "data/test_visuals_watched"
os.environ["BOBINE_THUMBNAILS_DIR"] = "data/test_visuals_thumbnails"

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.database import SessionLocal, init_db
from app.main import app
from app.media_assets.importer import import_asset
from app.media_assets.registry import BACKGROUNDS, COLLECTIONS, VISUALS
from app.models import Background, ImportSource, Visual


@pytest.fixture()
def visual(tmp_path):
    init_db()
    for folder in (settings.visuals_dir, settings.thumbnails_dir):
        Path(folder).mkdir(parents=True, exist_ok=True)
    source = tmp_path / "Affiche salle.png"
    Image.new("RGB", (64, 36), (200, 40, 40)).save(source)
    row = import_asset(VISUALS, str(source), source.name, ImportSource.upload)
    yield row
    with SessionLocal() as db:
        db.query(Visual).delete()
        db.commit()
    for folder in (settings.visuals_dir, settings.visuals_watch_dir, settings.thumbnails_dir):
        shutil.rmtree(folder, ignore_errors=True)


def test_a_visual_lives_in_its_own_folder_and_table(visual):
    assert Path(visual.file_path).parent == Path(settings.visuals_dir)
    assert Path(visual.file_path).name.startswith("vis_")
    with SessionLocal() as db:
        assert db.query(Visual).count() == 1
        assert db.query(Background).filter(Background.file_path == visual.file_path).count() == 0


def test_visual_routes_list_rename_and_delete(visual):
    client = TestClient(app)
    listed = client.get("/api/visuals").json()
    assert [(row["id"], row["title"], row["is_image"]) for row in listed] == [(visual.id, "Affiche salle", True)]
    assert all(row["file_path"] != visual.file_path for row in client.get("/api/backgrounds").json())
    assert client.put(f"/api/visuals/{visual.id}", json={"title": "Promo"}).json()["title"] == "Promo"
    assert client.get(f"/api/visuals/{visual.id}/stream").headers["content-type"] == "image/png"
    assert client.delete(f"/api/visuals/{visual.id}").status_code == 200
    assert not Path(visual.file_path).exists()
    assert client.get(f"/api/visuals/{visual.id}").status_code == 404


def test_every_space_has_its_own_folders_and_prefix():
    assert len({c.directory() for c in COLLECTIONS}) == len(COLLECTIONS)
    assert len({c.watch_directory() for c in COLLECTIONS}) == len(COLLECTIONS)
    assert len({c.file_prefix for c in COLLECTIONS}) == len(COLLECTIONS)
    assert BACKGROUNDS in COLLECTIONS and VISUALS in COLLECTIONS
