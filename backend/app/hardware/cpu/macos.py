import subprocess

from .guard import guarded


def _brand_string() -> str:
    return subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()


def cpu_name() -> str:
    return guarded(_brand_string)
