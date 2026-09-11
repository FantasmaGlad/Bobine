"""Handler du profil `linux-desktop` (app de bureau Linux, paquet .deb — cf.
CDC §6, plan §3).

Dans ce profil, Bobine tourne en session utilisateur (lancé au login par le
fichier .desktop autostart ou l'unité systemd utilisateur) avec BobineTray
comme superviseur local (cf. `backend/app/desktop/tray.py`).
`restart_services()` se contente de mettre fin au process courant (`os._exit(0)`) :
c'est le superviseur (BobineTray ou `Restart=always` systemd --user) qui le relance.
La désinstallation est déléguée au gestionnaire de paquets de la distribution
(`apt remove bobine`).
"""

import logging
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from app.utils.deployment import ProfileHandler, UpdateUnsupported

logger = logging.getLogger(__name__)


class LinuxDesktopHandler(ProfileHandler):
    profile = "linux-desktop"

    def _is_git_clone(self) -> bool:
        repo_dir = Path(__file__).resolve().parent.parent.parent.parent
        return (repo_dir / ".git").exists()

    def restart_services(self) -> None:
        logger.info("Arrêt du process pour redémarrage (relance attendue de BobineTray ou systemd --user).")
        # Sortie immédiate après l'envoi de la réponse HTTP de reset / mise à jour
        os._exit(0)

    def can_self_uninstall(self) -> bool:
        return False

    def uninstall_instructions(self) -> str:
        return (
            "Pour désinstaller Bobine, exécutez dans un terminal : "
            "sudo apt remove bobine (ou utilisez votre logithèque habituelle)."
        )

    def supports_git_versioning(self) -> bool:
        return self._is_git_clone()

    def can_auto_apply(self) -> bool:
        return True

    def apply_update(self, target_tag: str | None = None, download_url: str | None = None) -> None:
        repo_dir = Path(__file__).resolve().parent.parent.parent.parent
        if self._is_git_clone():
            if target_tag:
                subprocess.run(
                    ["git", "fetch", "--tags", "--force"],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=45,
                    check=True,
                )
                res = subprocess.run(
                    ["git", "checkout", target_tag],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                logger.info(f"git checkout {target_tag} (dev linux) : {res.stdout or res.stderr}")
            else:
                res = subprocess.run(
                    ["git", "pull", "--ff-only"],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                logger.info(f"git pull (dev linux) : {res.stdout}")
            self.restart_services()
            return

        # Environnement paquet installé .deb
        if not download_url:
            raise UpdateUnsupported(
                "Aucun lien de téléchargement disponible pour mettre à jour le paquet Linux (.deb)."
            )

        deb_file = Path(tempfile.gettempdir()) / "bobine_update.deb"
        logger.info(f"Téléchargement du paquet .deb depuis {download_url}...")
        urllib.request.urlretrieve(download_url, deb_file)

        # Lance l'installation polkit/dpkg en arrière-plan détaché
        cmd = f"sleep 1 && pkexec dpkg -i {deb_file}"
        subprocess.Popen(["sh", "-c", cmd], start_new_session=True)
        self.restart_services()
