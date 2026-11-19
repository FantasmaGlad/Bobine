import os
import sys

from .other import bundle_resources

__all__ = ["KEY", "bundle_resources", "open_folder", "prepare_console"]

KEY = "windows"


def open_folder(path: str) -> None:
    os.startfile(path)  # type: ignore[attr-defined]


def prepare_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, OSError, ValueError):
            pass
