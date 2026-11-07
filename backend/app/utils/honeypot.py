"""Leurre d'intrusion de l'appliance (décision M16).

`install.sh --honeypot` dépose hors du dépôt, dans `/var/lib/bobine/leurre/`, un fichier `LISEZ-MOI.txt` qui demande de
créer `bom.txt` avec une ligne fixe. Aucun secret n'est demandé. Quiconque suit cette consigne (un assistant automatique qui
lit les fichiers d'une machine qu'il explore, par exemple) fait apparaître `bom.txt` : le backend l'enregistre au journal
d'activité (`intrusion_suspected`) et le diagnostic signale `honeypot_triggered`.

Actif seulement sur l'appliance (profil `linux-headless`) et seulement si `LISEZ-MOI.txt` est présent : sans l'option
d'installation, rien n'est surveillé. Le dossier peut être changé par `BOBINE_HONEYPOT_DIR` (essais).
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DIRECTORY = "/var/lib/bobine/leurre"
NOTICE_NAME = "LISEZ-MOI.txt"
TRIGGER_NAME = "bom.txt"
POLL_SECONDS = 20.0
REPORTED_KEY = "honeypot_reported"  # horodatage (ns) de la création déjà signalée

_task: asyncio.Task | None = None


def directory() -> Path:
    return Path(os.environ.get("BOBINE_HONEYPOT_DIR") or DEFAULT_DIRECTORY)


def is_armed() -> bool:
    return (directory() / NOTICE_NAME).is_file()


def trigger_signature() -> str | None:
    """Identifiant de la création de `bom.txt` (inode et date) ; `None` s'il n'existe pas ou si le leurre est absent."""
    if not is_armed():
        return None
    try:
        stat = (directory() / TRIGGER_NAME).stat()
    except OSError:
        return None
    return f"{stat.st_ino}:{stat.st_mtime_ns}"


def is_triggered() -> bool:
    return trigger_signature() is not None


def status() -> dict[str, bool]:
    return {"armed": is_armed(), "triggered": is_triggered()}


def report_once() -> bool:
    """Journalise une apparition de `bom.txt` une seule fois (même après un redémarrage) ; vrai si elle est nouvelle."""
    from app.database import SessionLocal
    from app.models import Setting
    from app.utils.activity_log import log_activity

    signature = trigger_signature()
    if signature is None:
        return False
    with SessionLocal() as db:
        row = db.query(Setting).filter(Setting.key == REPORTED_KEY).first()
        if row is not None and row.value == signature:
            return False
        if row is None:
            db.add(Setting(key=REPORTED_KEY, value=signature))
        else:
            row.value = signature
        db.commit()
        log_activity(db, "intrusion_suspected", f"{TRIGGER_NAME} créé dans le dossier leurre {directory()}")
    logger.warning("Leurre d'intrusion déclenché : %s a été créé dans %s", TRIGGER_NAME, directory())
    return True


async def _watch() -> None:
    while True:
        try:
            await asyncio.get_running_loop().run_in_executor(None, report_once)
        except Exception as exc:  # la surveillance ne doit jamais gêner Bobine
            logger.debug("Surveillance du leurre : %s", exc)
        await asyncio.sleep(POLL_SECONDS)


def start() -> bool:
    """Lance la surveillance sur l'appliance quand le leurre est en place ; renvoie vrai si elle tourne."""
    global _task
    from app.utils.deployment import get_deployment_profile

    if _task is not None and not _task.done():
        return True
    if get_deployment_profile() != "linux-headless" or not is_armed():
        return False
    _task = asyncio.get_running_loop().create_task(_watch(), name="bobine-honeypot")
    return True


async def stop() -> None:
    global _task
    task, _task = _task, None
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
