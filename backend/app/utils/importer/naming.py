"""Titre, programme et version tirés du nom d'un fichier."""
from pathlib import Path


def parse_title_program_release(original_filename: str) -> tuple[str, str | None, str | None]:
    """Titre propre, programme (RPM, Sprint, The Trip) et release déduits du nom d'un fichier de cours."""
    import re

    title = Path(original_filename).stem.replace("_", " ").replace("-", " ")
    program = None
    release = None
    title_upper = title.upper()
    if "RPM" in title_upper:
        program = "RPM"
    elif "SPRINT" in title_upper:
        program = "Sprint"
    elif "TRIP" in title_upper or "THE TRIP" in title_upper:
        program = "The Trip"
    match = re.search(r"\b\d{1,3}\b", title)
    if match:
        release = match.group(0)
    return title, program, release
