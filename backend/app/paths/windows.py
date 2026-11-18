import os
from pathlib import Path


def _program_data() -> Path | None:
    program_data = os.environ.get("ProgramData")
    return Path(program_data) / "Bobine" if program_data else None


def data_root() -> Path | None:
    return _program_data()


def global_config_path() -> Path | None:
    base = _program_data()
    return base / "config.toml" if base else None
