import subprocess

SUFFIX = ".exe"


def hidden_console_kwargs() -> dict:
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def tied_to_parent_kwargs() -> dict:
    return hidden_console_kwargs()


def restrict_directory(path) -> None:
    return None
