import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

from app.api.routes.settings import maintenance  # noqa: E402
from app.config import DATA_DIRS  # noqa: E402


def test_every_data_folder_counts_in_the_application_size(monkeypatch, tmp_path):
    for name in DATA_DIRS:
        folder = tmp_path / name
        folder.mkdir()
        (folder / "fichier").write_bytes(b"x" * 10)
        monkeypatch.setattr(maintenance.runtime_settings, name, str(folder))
    assert maintenance.get_storage()["app_bytes"] == 10 * len(DATA_DIRS)
