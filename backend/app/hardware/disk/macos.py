from .command import first_line


def _media_name(line: str) -> str:
    return line.split(":", 1)[1].strip() if "Device / Media Name:" in line else ""


def storage_model() -> str:
    return first_line(["diskutil", "info", "/"], 2, _media_name)
