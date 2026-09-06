"""Handler du profil `linux-headless` (l'appliance Debian existante,
`install.sh`) — comportement inchangé par rapport à ce qui existait avant
PortabiliteCrossPlatformX : `sudo systemctl restart`, enveloppe de
désinstallation `systemd-run`, mise à jour via `git pull`."""

import logging
import subprocess
from pathlib import Path

from app.utils.deployment import (
    BACKEND_SERVICE_UNIT,
    KIOSK_SERVICE_UNIT,
    ProfileHandler,
)

logger = logging.getLogger(__name__)

UNINSTALL_WRAPPER = Path("/usr/local/sbin/bobine-uninstall")


class LinuxHeadlessHandler(ProfileHandler):
    profile = "linux-headless"

    def restart_services(self) -> None:
        for unit in (KIOSK_SERVICE_UNIT, BACKEND_SERVICE_UNIT):
            try:
                subprocess.run(["sudo", "systemctl", "restart", unit], check=True, timeout=15)
                logger.info(f"Service {unit} redémarré")
            except Exception as e:
                logger.error(f"Échec du redémarrage de {unit} (hors environnement cible ?) : {e}")

    def can_self_uninstall(self) -> bool:
        return True

    def start_uninstall(self) -> None:
        subprocess.Popen(["sudo", str(UNINSTALL_WRAPPER)], start_new_session=True)
        logger.info("Désinstallation déclenchée (enveloppe systemd-run détachée).")

    def uninstall_instructions(self) -> str:
        # Non utilisé : can_self_uninstall() est True pour ce profil.
        return ""

    def supports_git_versioning(self) -> bool:
        return True

    def apply_update(self) -> None:
        repo_dir = Path(__file__).resolve().parent.parent.parent.parent
        res = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=45,
        )
        logger.info(f"git pull résultat : {res.stdout}")
        self.restart_services()
