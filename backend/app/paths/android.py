import os
from pathlib import Path

from .common import ensure_dir


def data_root() -> Path | None:
    android_data_dir = os.environ.get("BOBINE_ANDROID_DATA_DIR")
    return ensure_dir(Path(android_data_dir)) if android_data_dir else None


def global_config_path() -> Path | None:
    return None
