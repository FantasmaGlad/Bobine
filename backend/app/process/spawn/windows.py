import subprocess

SUFFIX = ".exe"


def hidden_console_kwargs() -> dict:
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
