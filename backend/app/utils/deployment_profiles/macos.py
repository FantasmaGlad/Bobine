"""Handler du profil `macos` (app de bureau macOS, bundle `.app` — cf.
CDC §7, plan §4).

Comme Windows (Lot 1) et Linux de bureau (Lot 2) : BobineTray supervise
BobineBackend en process enfant, aucun équivalent de service système
(launchd géré par l'utilisateur via LaunchAgent, pas de daemon root).
`restart_services()` se contente de mettre fin au process courant
(`os._exit(0)`) : c'est BobineTray (relancé lui-même par launchd si le
LaunchAgent a `KeepAlive` actif) qui le relance. La désinstallation est
manuelle (glisser `Bobine.app` vers la Corbeille), comme toute app macOS
non distribuée par le Mac App Store.
"""

import logging
import os

from app.utils.deployment import ProfileHandler, UpdateUnsupported

logger = logging.getLogger(__name__)


class MacOSHandler(ProfileHandler):
    profile = "macos"

    def restart_services(self) -> None:
        logger.info("Arrêt du process pour redémarrage (relance attendue de BobineTray/LaunchAgent).")
        # Sortie immédiate après l'envoi de la réponse HTTP de reset / mise à jour
        os._exit(0)

    def can_self_uninstall(self) -> bool:
        return False

    def uninstall_instructions(self) -> str:
        return (
            "Quittez Bobine (icône de la barre de menus > Quitter), faites glisser "
            "Bobine.app depuis le dossier Applications vers la Corbeille, puis supprimez "
            "~/Library/LaunchAgents/com.bobine.app.plist pour désactiver le lancement automatique."
        )

    def supports_git_versioning(self) -> bool:
        return False

    def apply_update(self, target_tag: str | None = None) -> None:
        raise UpdateUnsupported(
            "La mise à jour automatique n'est pas encore disponible sur macOS — "
            "téléchargez et installez la dernière version depuis les releases GitHub "
            "du projet (github.com/FantasmaGlad/Bobine/releases)."
        )
