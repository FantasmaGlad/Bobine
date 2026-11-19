import subprocess
from pathlib import Path

from .other import prepare_console

__all__ = ["KEY", "bundle_resources", "open_folder", "prepare_console"]

KEY = "macos"


def open_folder(path: str) -> None:
    subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def bundle_resources(executable: Path) -> Path:
    return executable.parent.parent / "Resources"
