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

from app.utils.deployment import ProfileHandler, UpdateUnsupported

logger = logging.getLogger(__name__)


class LinuxDesktopHandler(ProfileHandler):
    profile = "linux-desktop"

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
        return False

    def apply_update(self, target_tag: str | None = None) -> None:
        raise UpdateUnsupported(
            "La mise à jour automatique n'est pas encore disponible sur "
            "Linux (bureau) — téléchargez et installez le dernier paquet .deb "
            "depuis les releases GitHub du projet "
            "(github.com/FantasmaGlad/Bobine/releases) ou mettez à jour via apt."
        )
