"""Lecture directe d'un conteneur MP4 : durée et position de l'index (faststart)."""
import os
import logging


logger = logging.getLogger(__name__)


def is_faststart_mp4(file_path: str) -> bool:
    """Vrai si l'atome 'moov' (index des échantillons) précède l'atome 'mdat' (données) dans le fichier — condition requise pour qu'un navigateur puisse décoder la moindre image avant d'avoir reçu la quasi-totalité du fichier."""
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


def read_mp4_duration_seconds(file_path: str) -> float | None:
    """Lit la durée d'un MP4/M4V directement dans l'atome 'mvhd' (imbriqué dans 'moov'), sans ffprobe — repli utilisé quand ffprobe est indisponible pour au moins récupérer la durée, seule métadonnée manquante qu'un parcours d'en-têtes pur Python peut raisonnablement reconstituer (largeur/hauteur/codec demanderaient de décoder les box 'stsd', bien plus engagé pour un gain d'affichage secondaire)."""
    try:
        with open(file_path, "rb") as f:
            file_size = os.fstat(f.fileno()).st_size

            def find_child_box(start: int, end: int, target: bytes) -> tuple[int, int] | None:
                """Cherche `target` parmi les boîtes enfants directes de l'intervalle [start, end) ; renvoie (offset_contenu, taille_contenu)."""
                pos = start
                while pos < end:
                    f.seek(pos)
                    header = f.read(8)
                    if len(header) < 8:
                        return None
                    size = int.from_bytes(header[0:4], "big")
                    box_type = header[4:8]
                    header_len = 8
                    if size == 1:
                        ext = f.read(8)
                        if len(ext) < 8:
                            return None
                        size = int.from_bytes(ext, "big")
                        header_len = 16
                    elif size == 0:
                        size = end - pos
                    if size < header_len:
                        return None
                    if box_type == target:
                        return pos + header_len, size - header_len
                    pos += size
                return None

            moov = find_child_box(0, file_size, b"moov")
            if moov is None:
                return None
            moov_start, moov_size = moov

            mvhd = find_child_box(moov_start, moov_start + moov_size, b"mvhd")
            if mvhd is None:
                return None
            mvhd_start, _ = mvhd

            f.seek(mvhd_start)
            version_flags = f.read(4)
            if len(version_flags) < 4:
                return None
            version = version_flags[0]
            if version == 1:
                f.seek(mvhd_start + 4 + 16)
                rest = f.read(12)
                if len(rest) < 12:
                    return None
                timescale = int.from_bytes(rest[0:4], "big")
                duration = int.from_bytes(rest[4:12], "big")
            else:
                f.seek(mvhd_start + 4 + 8)
                rest = f.read(8)
                if len(rest) < 8:
                    return None
                timescale = int.from_bytes(rest[0:4], "big")
                duration = int.from_bytes(rest[4:8], "big")

            if not timescale:
                return None
            return duration / timescale
    except OSError as e:
        logger.warning(f"Impossible de lire la durée MP4 (mvhd) de {file_path} : {e}")
        return None
