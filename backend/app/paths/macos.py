from pathlib import Path

from .common import ensure_dir


def _support() -> Path:
    return Path.home() / "Library" / "Application Support" / "Bobine"


def bundle_root(executable_dir: Path) -> Path:
    return executable_dir.parent / "Resources"


def data_root() -> Path | None:
    return ensure_dir(_support())


def global_config_path() -> Path | None:
    return _support() / "config.toml"
