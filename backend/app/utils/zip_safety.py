"""Extraction sûre d'archives ZIP (réf. CDC sécurité 2026-09, correctif
zip-slip) — un membre nommé `../../etc/x` (ou équivalent) fait normalement
écrire `ZipFile.extractall()` hors du dossier de destination prévu, sans
qu'aucune vérification native ne s'y oppose."""

import zipfile
from pathlib import Path


class UnsafeZipError(Exception):
    """Levée quand une archive contient un membre qui sortirait du dossier de destination."""


def safe_extract_zip(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    """
    Équivalent sûr de `zf.extractall(dest_dir)` : vérifie D'ABORD que chaque
    membre de l'archive résout bien sous `dest_dir` avant d'extraire quoi que
    ce soit — une archive malveillante ne doit laisser AUCUN fichier sur
    disque, pas juste s'arrêter au milieu de l'extraction.
    """
    dest_dir = dest_dir.resolve()
    for member in zf.namelist():
        resolved = (dest_dir / member).resolve()
        if resolved != dest_dir and dest_dir not in resolved.parents:
            raise UnsafeZipError(
                f"Archive ZIP invalide : le membre « {member} » sortirait du dossier de destination."
            )
    zf.extractall(dest_dir)
