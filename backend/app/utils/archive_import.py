"""Import d'une archive de médias (vidéos, fonds animés) : extraction sûre puis un import par fichier, dans une seule tâche."""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Callable

from app.utils.import_jobs import JobCancelledError, is_job_cancelled, update_job
from app.utils.zip_safety import InvalidArchiveError, UnsafeZipError, safe_extract_archive

logger = logging.getLogger(__name__)


def import_media_archive(
    archive_path: str,
    job_id: str | None,
    extensions: frozenset[str] | set[str],
    import_one: Callable[[str, str], object],
    kind: str,
) -> list[object]:
    """Extrait l'archive puis appelle `import_one(chemin, nom)` pour chaque fichier dont l'extension est acceptée."""
    update_job(job_id, stage="extracting")
    imported: list[object] = []
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="bobine_archive_") as tmp_dir:
        try:
            safe_extract_archive(Path(archive_path), Path(tmp_dir))
        except InvalidArchiveError:
            raise
        except UnsafeZipError as exc:
            raise ValueError(str(exc)) from exc
        finally:
            if os.path.exists(archive_path):
                os.remove(archive_path)

        files = sorted(
            p for p in Path(tmp_dir).rglob("*")
            if p.is_file() and p.suffix.lower() in extensions and not p.name.startswith(".") and "__MACOSX" not in p.parts
        )
        if not files:
            raise ValueError(f"Aucun fichier {kind} trouvé dans l'archive.")
        update_job(job_id, files_total=len(files), files_done=0)
        for path in files:
            if is_job_cancelled(job_id):
                raise JobCancelledError()
            try:
                imported.append(import_one(str(path), path.name))
                update_job(job_id, files_done=len(imported))
            except JobCancelledError:
                raise
            except Exception as exc:
                logger.warning("Import de %r depuis l'archive refusé : %s", path.name, exc)
                failures.append(f"{path.name!r} : {exc}")
    if not imported:
        raise ValueError("Aucun fichier de l'archive n'a pu être importé. " + " ; ".join(failures[:3]))
    return imported
