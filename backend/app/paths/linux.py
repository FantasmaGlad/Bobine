import os
import sys
from pathlib import Path

from .common import ensure_dir


def data_root(root_dir: Path) -> Path | None:
    if getattr(sys, "frozen", False) or not os.access(root_dir, os.W_OK) or os.environ.get("BOBINE_USE_XDG") == "1":
        xdg_data = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
        return ensure_dir(base / "bobine")
    return None


def global_config_path() -> Path | None:
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    user_config = (Path(xdg_config) if xdg_config else Path.home() / ".config") / "bobine" / "config.toml"
    return user_config if user_config.exists() else None
