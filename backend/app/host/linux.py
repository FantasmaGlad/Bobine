import subprocess

from .other import KEY, bundle_resources, prepare_console

__all__ = ["KEY", "bundle_resources", "open_folder", "prepare_console"]


def open_folder(path: str) -> None:
    subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
