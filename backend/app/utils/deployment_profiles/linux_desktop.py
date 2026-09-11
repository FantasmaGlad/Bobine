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
        logger.info("Déclenchement du redémarrage du service bureau Linux (BobineTray ou systemd --user)...")
        # Programme une tentative de relance systemd --user en tâche détachée
        cmd = "sleep 1 && (systemctl --user restart bobine.service || systemctl --user restart bobine || true)"
        try:
            subprocess.Popen(["sh", "-c", cmd], start_new_session=True)
        except Exception as e:
            logger.debug(f"Relance systemctl --user non disponible : {e}")

        # Délai de 1.5s avant os._exit(0) pour laisser l'API HTTP répondre
        import threading
        import time

        def _delayed_exit():
            time.sleep(1.5)
            os._exit(0)

        threading.Thread(target=_delayed_exit, daemon=True).start()

    def can_self_uninstall(self) -> bool:
        return True

    def start_uninstall(self) -> None:
        repo_dir = Path(__file__).resolve().parent.parent.parent.parent
        if self._is_git_clone() and (repo_dir / "install.sh").exists():
            cmd = "sleep 1 && pkexec ./install.sh --uninstall --purge --purge-data -y"
            subprocess.Popen(["sh", "-c", cmd], cwd=repo_dir, start_new_session=True)
        else:
            cmd = "sleep 1 && (pkexec apt-get remove -y bobine || pkexec dpkg -P bobine || pkexec dpkg -r bobine)"
            subprocess.Popen(["sh", "-c", cmd], start_new_session=True)
        logger.info("Désinstallation Linux desktop déclenchée en tâche de fond via pkexec.")

    def uninstall_instructions(self) -> str:
        return (
            "Pour désinstaller Bobine manuellement, exécutez dans un terminal : "
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

        # Lance l'installation polkit/dpkg en arrière-plan détaché.
        # prerm arrête proprement BobineBackend/BobineTray, puis postinst relance
        # automatiquement l'application pour la session utilisateur.
        # Ne PAS appeler self.restart_services() ici : cela tuerait le backend
        # prématurément avant que pkexec n'ait pu authentifier l'utilisateur.
        cmd = f"sleep 1 && pkexec dpkg -i {deb_file}"
        subprocess.Popen(["sh", "-c", cmd], start_new_session=True)
