"""Handler du profil `windows` (app de bureau, .exe PyInstaller +
installeur Inno Setup — cf. CDC §5, plan §2).

Pas de service Windows dans ce profil (décision #1 du CDC : app de bureau
lancée par un utilisateur connecté, pas une « boîte noire » sans
supervision) — la supervision du process backend est assurée par
`BobineTray` (cf. `backend/app/desktop/tray.py`), qui relance
`BobineBackend.exe` s'il s'arrête. `restart_services()` se contente donc de
mettre fin proprement au process courant : c'est `BobineTray` qui le
relance, exactement comme il le ferait pour un arrêt inattendu — aucun
canal de communication dédié entre le backend et le tray n'est nécessaire.
"""

import logging
import os

from app.utils.deployment import ProfileHandler, UpdateUnsupported

logger = logging.getLogger(__name__)


class WindowsHandler(ProfileHandler):
    profile = "windows"

    def restart_services(self) -> None:
        logger.info("Arrêt du process pour redémarrage (relance attendue de BobineTray).")
        # Sortie immédiate plutôt qu'un arrêt FastAPI/uvicorn « propre » :
        # ce code tourne déjà dans une tâche de fond après l'envoi de la
        # réponse HTTP (cf. routers/settings.py::_run_full_reset), il n'y a
        # plus rien à répondre proprement. `os._exit` évite en plus tout
        # risque qu'un `finally`/gestionnaire de signal ne bloque l'arrêt.
        os._exit(0)

    def can_self_uninstall(self) -> bool:
        return False

    def uninstall_instructions(self) -> str:
        return (
            "Ouvrez « Applications et fonctionnalités » dans les paramètres "
            "Windows (ou exécutez le désinstalleur dans le dossier "
            "d'installation de Bobine) pour retirer l'application."
        )

    def supports_git_versioning(self) -> bool:
        return False

    def apply_update(self, target_tag: str | None = None) -> None:
        raise UpdateUnsupported(
            "La mise à jour automatique n'est pas encore disponible sur "
            "Windows — téléchargez et exécutez le dernier installeur "
            "depuis les releases GitHub du projet "
            "(github.com/FantasmaGlad/Bobine/releases)."
        )
