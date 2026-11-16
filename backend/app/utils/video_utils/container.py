"""Lecture directe d'un conteneur MP4 : durée et position de l'index (faststart)."""
import os
import logging


logger = logging.getLogger(__name__)


def is_faststart_mp4(file_path: str) -> bool:
    """Vrai si l'atome 'moov' (index des échantillons) précède l'atome 'mdat'."""
    try:
        with open(file_path, "rb") as f:
            file_size = os.fstat(f.fileno()).st_size
            pos = 0
            while pos < file_size:
                header = f.read(8)
                if len(header) < 8:
                    break
                size = int.from_bytes(header[0:4], "big")
                box_type = header[4:8].decode("ascii", errors="ignore")
                if box_type == "moov":
                    return True
                if box_type == "mdat":
                    return False
                if size == 1:
                    ext = f.read(8)
                    if len(ext) < 8:
                        break
                    size = int.from_bytes(ext, "big")
                elif size == 0:
                    break
                if size < 8:
                    break
                pos += size
                f.seek(pos)
    except OSError as e:
        logger.warning(f"Impossible de vérifier l'ordre des atomes MP4 de {file_path} : {e}")
    return False


def _box_header(f, pos: int, end: int) -> tuple[int, int, bytes] | None:
    """(taille totale, longueur de l'en-tête, type) de la boîte qui commence à `pos`."""
    f.seek(pos)
    header = f.read(8)
    if len(header) < 8:
        return None
    size, box_type, header_len = int.from_bytes(header[0:4], "big"), header[4:8], 8
    if size == 1:
        ext = f.read(8)
        if len(ext) < 8:
            return None
        size, header_len = int.from_bytes(ext, "big"), 16
    elif size == 0:
        size = end - pos
    return (size, header_len, box_type) if size >= header_len else None


def _find_child_box(f, start: int, end: int, target: bytes) -> tuple[int, int] | None:
    """Cherche `target` parmi les boîtes enfants directes de [start, end) ; renvoie (offset_contenu, taille_contenu)."""
    pos = start
    while pos < end:
        box = _box_header(f, pos, end)
        if box is None:
            return None
        size, header_len, box_type = box
        if box_type == target:
            return pos + header_len, size - header_len
        pos += size
    return None


def _mvhd_duration(f, mvhd_start: int) -> float | None:
    f.seek(mvhd_start)
    version_flags = f.read(4)
    if len(version_flags) < 4:
        return None
    skip, width = (16, 8) if version_flags[0] == 1 else (8, 4)
    f.seek(mvhd_start + 4 + skip)
    rest = f.read(4 + width)
    if len(rest) < 4 + width:
        return None
    timescale = int.from_bytes(rest[0:4], "big")
    duration = int.from_bytes(rest[4:4 + width], "big")
    return duration / timescale if timescale else None


def read_mp4_duration_seconds(file_path: str) -> float | None:
    """Lit la durée d'un MP4/M4V directement dans l'atome 'mvhd'."""
    try:
        with open(file_path, "rb") as f:
            moov = _find_child_box(f, 0, os.fstat(f.fileno()).st_size, b"moov")
            if moov is None:
                return None
            mvhd = _find_child_box(f, moov[0], moov[0] + moov[1], b"mvhd")
            return None if mvhd is None else _mvhd_duration(f, mvhd[0])
    except OSError as e:
        logger.warning(f"Impossible de lire la durée MP4 (mvhd) de {file_path} : {e}")
        return None
