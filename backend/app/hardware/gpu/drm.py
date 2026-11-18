import glob

from .common import probe, read_text


def busy_percent() -> float | None:
    for path in glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"):
        value = probe(lambda path=path: read_text(path))
        if value and value.isdigit():
            return float(value)
    return None
