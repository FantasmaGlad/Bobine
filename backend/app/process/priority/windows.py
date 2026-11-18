import subprocess


def popen_kwargs() -> dict:
    return {"creationflags": getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)}


def lower(pid: int) -> None:
    return None
