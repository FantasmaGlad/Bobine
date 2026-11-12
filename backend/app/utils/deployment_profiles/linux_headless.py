"""Handler du profil `linux-headless` (l'appliance Debian existante, `install.sh`) : `sudo systemctl restart`, enveloppe de désinstallation `systemd-run`, mise à jour via `git checkout`/`git pull`."""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Callable

from app.utils.deployment import (
    BACKEND_SERVICE_UNIT,
    KIOSK_SERVICE_UNIT,
    ProfileHandler,
)
from app.updates.orchestrator import run_checked

logger = logging.getLogger(__name__)

UNINSTALL_WRAPPER = Path("/usr/local/sbin/bobine-uninstall")

_NOOP_REPORT: Callable[..., None] = lambda *a, **k: None  # noqa: E731


def _repo_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


UPDATE_CONFIRMATION_SECONDS = 180
PENDING_UPDATE_FILE = "update-pending.json"


def write_pending_update(repo_dir: Path, previous_ref: str) -> None:
    """Demande au chien de garde de confirmer la mise à jour ou de revenir à `previous_ref`."""
    marker = repo_dir / "backend" / PENDING_UPDATE_FILE
    try:
        marker.write_text(
            json.dumps({
                "previous_ref": previous_ref,
                "deadline": int(time.time()) + UPDATE_CONFIRMATION_SECONDS,
                "pid": os.getpid(),
            }),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Retour arrière automatique non armé : %s", exc)


class LinuxHeadlessHandler(ProfileHandler):
    profile = "linux-headless"

    def restart_services(self) -> None:
        cmd = (
            "sleep 1 && "
            "(sudo /usr/bin/systemctl restart bobine-kiosk.service || sudo systemctl restart bobine-kiosk.service || true) && "
            "(sudo /usr/bin/systemctl restart bobine-backend.service || sudo systemctl restart bobine-backend.service || true)"
        )
        try:
            subprocess.Popen(["sh", "-c", cmd], start_new_session=True)
            logger.info("Redémarrage asynchrone des services programmé (bobine-kiosk, bobine-backend)")
        except Exception as e:
            logger.error(f"Échec de programmation du redémarrage : {e}")

    def _restart_services_checked(self, report: Callable[..., None]) -> None:
        report("restarting", message="Redémarrage des services…")
        for unit in (KIOSK_SERVICE_UNIT, BACKEND_SERVICE_UNIT):
            try:
                run_checked(["sudo", "systemctl", "restart", unit], timeout=20)
            except Exception as e:
                raise RuntimeError(f"Échec du redémarrage de {unit} : {e}") from e
            try:
                is_active = run_checked(["systemctl", "is-active", unit], timeout=10)
                if is_active.stdout.strip() != "active":
                    raise RuntimeError(f"{unit} redémarré mais n'est pas actif ({is_active.stdout.strip()})")
            except Exception as e:
                raise RuntimeError(f"Échec de vérification de {unit} après redémarrage : {e}") from e

    def can_self_uninstall(self) -> bool:
        return True

    def start_uninstall(self) -> None:
        subprocess.Popen(["sudo", str(UNINSTALL_WRAPPER)], start_new_session=True)
        logger.info("Désinstallation déclenchée (enveloppe systemd-run détachée).")

    def uninstall_instructions(self) -> str:
        return ""

    def supports_git_versioning(self) -> bool:
        return True

    def supports_update_over_tor(self) -> bool:
        return False

    def has_system_port80_redirect(self) -> bool:
        return True

    def can_schedule_auto_apply(self) -> bool:
        return True

    def apply_update(
        self,
        target_tag: str | None = None,
        download_url: str | None = None,
        asset_digest: str | None = None,
        report: Callable[..., None] | None = None,
    ) -> None:
        report = report or _NOOP_REPORT
        repo_dir = _repo_dir()

        previous_ref = self._current_ref(repo_dir)

        report("checking", message="Récupération de la nouvelle version…")
        if target_tag:
            run_checked(["git", "fetch", "--tags", "--force"], cwd=repo_dir, timeout=45)
            run_checked(["git", "checkout", target_tag], cwd=repo_dir, timeout=45)
            logger.info(f"git checkout {target_tag} effectué avec succès.")
        else:
            run_checked(["git", "pull", "--ff-only"], cwd=repo_dir, timeout=45)
            logger.info("git pull --ff-only effectué avec succès.")

        try:
            self._rebuild(repo_dir, report)
        except Exception as e:
            if self._rollback(repo_dir, previous_ref):
                outcome = f"version précédente restaurée ({previous_ref[:12]}), l'appliance continue de fonctionner sur l'ancienne version."
            else:
                outcome = f"le retour à la version précédente ({previous_ref[:12]}) a échoué : relancez l'installateur."
            raise RuntimeError(f"{e} — {outcome}") from e

        write_pending_update(repo_dir, previous_ref)

        self._restart_services_checked(report)

    @staticmethod
    def _current_ref(repo_dir: Path) -> str:
        try:
            branch = run_checked(["git", "symbolic-ref", "--short", "-q", "HEAD"], cwd=repo_dir, timeout=10)
            if branch.stdout.strip():
                return branch.stdout.strip()
        except Exception as exc:
            logger.debug("_current_ref : %s", exc)
        return run_checked(["git", "rev-parse", "HEAD"], cwd=repo_dir, timeout=10).stdout.strip()

    @staticmethod
    def _rollback(repo_dir: Path, previous_ref: str) -> bool:
        try:
            run_checked(["git", "checkout", previous_ref], cwd=repo_dir, timeout=45)
            logger.warning(f"Mise à jour annulée : retour à {previous_ref}.")
            return True
        except Exception as rollback_error:
            logger.error(f"Échec du retour arrière vers {previous_ref} : {rollback_error}")
            return False

    def _rebuild(self, repo_dir: Path, report: Callable[..., None]) -> None:
        venv_pip = repo_dir / "backend" / ".venv" / "bin" / "pip"
        if venv_pip.exists():
            report("installing", message="Mise à jour des dépendances serveur…")
            run_checked(
                [str(venv_pip), "install", "-q", "-r", str(repo_dir / "backend" / "requirements.txt")],
                timeout=300,
            )
        else:
            logger.warning(f"Environnement virtuel introuvable ({venv_pip}) — étape pip ignorée.")

        report("installing", message="Reconstruction de l'interface (plusieurs minutes sur ce matériel)…")
        run_checked(["npm", "ci", "--no-audit", "--no-fund"], cwd=repo_dir / "frontend", timeout=900)
        run_checked(["npm", "run", "build"], cwd=repo_dir / "frontend", timeout=1200)
