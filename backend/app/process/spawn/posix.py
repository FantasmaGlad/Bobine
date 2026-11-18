import os

SUFFIX = ""


def hidden_console_kwargs() -> dict:
    return {}


def tied_to_parent_kwargs() -> dict:
    return {}


def restrict_directory(path) -> None:
    os.chmod(path, 0o700)
