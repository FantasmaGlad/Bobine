#!/usr/bin/env python3
"""Unifie les données sous ``${REPO}/data``."""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_LEGACY_SUBDIRS = ("audio", "audio_watched", "backgrounds", "backgrounds_watched", "logs")

_PATH_COLUMNS = (("audio_tracks", "file_path"), ("backgrounds", "file_path"))


def _backup_database(db_path: Path, dry: bool, log) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = db_path.with_name(f"{db_path.name}.premigration-{ts}")
    log(f"  Sauvegarde de la base : {backup}")
    if dry:
        return
    try:
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(backup))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
    except sqlite3.Error:
        shutil.copy2(db_path, backup)


def _move_contents(src: Path, dst: Path, dry: bool, log) -> int:
    moved = 0
    if not dry:
        dst.mkdir(parents=True, exist_ok=True)
    for entry in sorted(src.iterdir()):
        target = dst / entry.name
        if target.exists():
            log(f"    ! {entry.name} déjà présent à la cible — laissé dans {src}")
            continue
        log(f"    déplace {entry.name} -> {target}")
        if not dry:
            shutil.move(str(entry), str(target))
        moved += 1
    return moved


def run_migration(repo_dir: Path, db_path: Path | None, configured_audio_dir: Path, dry: bool, log=print) -> int:
    """Cœur testable de la migration."""
    legacy_root = (repo_dir / "backend" / "data").resolve()
    target_root = (repo_dir / "data").resolve()

    if legacy_root == target_root:
        log("Aucune migration nécessaire (source et cible identiques).")
        return 0

    expected_audio = (target_root / "audio").resolve()
    if configured_audio_dir.resolve() != expected_audio:
        log(f"ERREUR : config.audio_dir = {configured_audio_dir} (attendu {expected_audio}).")
        log("Lance d'abord ./install.sh (il met à jour config.toml), puis relance cette migration.")
        return 1

    if not legacy_root.exists():
        log(f"Aucun dossier hérité à migrer ({legacy_root} absent). Rien à faire.")
        return 0

    log(f"Migration des données héritées : {legacy_root} -> {target_root}")
    if dry:
        log("[DRY-RUN] aucune modification ne sera écrite.")

    if db_path and db_path.exists():
        _backup_database(db_path, dry, log)

    total = 0
    for sub in _LEGACY_SUBDIRS:
        src = legacy_root / sub
        if not src.exists():
            continue
        log(f"  Dossier {sub} :")
        total += _move_contents(src, target_root / sub, dry, log)
        if not dry:
            try:
                src.rmdir()
            except OSError:
                pass
    if not dry:
        try:
            legacy_root.rmdir()
        except OSError:
            pass

    if db_path and db_path.exists():
        legacy_prefix = str(legacy_root) + os.sep
        target_prefix = str(target_root) + os.sep
        log(f"  Réécriture des chemins en base : {legacy_prefix} -> {target_prefix}")
        if not dry:
            conn = sqlite3.connect(str(db_path))
            try:
                cur = conn.cursor()
                for table, col in _PATH_COLUMNS:
                    try:
                        n = cur.execute(
                            f"UPDATE {table} SET {col} = REPLACE({col}, ?, ?) WHERE {col} LIKE ?",
                            (legacy_prefix, target_prefix, legacy_prefix + "%"),
                        ).rowcount
                        log(f"    {table}.{col} : {n} ligne(s) réécrite(s)")
                    except sqlite3.OperationalError as e:
                        log(f"    {table} : ignoré ({e})")
                conn.commit()
            finally:
                conn.close()

    log(f"Migration terminée : {total} élément(s) déplacé(s).")
    return 0


def main() -> int:
    dry = "--dry-run" in sys.argv[1:]
    repo_dir = Path(os.environ.get("OLMC_MIGRATE_REPO_DIR", Path(__file__).resolve().parent.parent))
    backend_dir = repo_dir / "backend"
    sys.path.insert(0, str(backend_dir))

    from app.config import settings

    db_path = None
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url[len("sqlite:///"):])

    return run_migration(repo_dir, db_path, Path(settings.audio_dir), dry)


if __name__ == "__main__":
    sys.exit(main())
