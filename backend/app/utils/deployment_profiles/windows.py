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
        return True

    def start_uninstall(self) -> None:
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        app_dir = (
            Path(sys.executable).parent
            if getattr(sys, "frozen", False)
            else Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Bobine"
        )
        uninstaller = app_dir / "unins000.exe"
        temp_dir = Path(tempfile.gettempdir())
        batch_path = temp_dir / "bobine_uninstall_runner.bat"
        batch_content = f"""@echo off
timeout /t 2 /nobreak > NUL
if exist "{uninstaller}" (
    start "" "{uninstaller}"
)
del "%~f0" > NUL 2>&1
"""
        batch_path.write_text(batch_content, encoding="latin1")
        creationflags = 0
        if hasattr(subprocess, "DETACHED_PROCESS"):
            creationflags |= subprocess.DETACHED_PROCESS
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(["cmd.exe", "/c", str(batch_path)], creationflags=creationflags, close_fds=True)
        self.restart_services()

    def uninstall_instructions(self) -> str:
        return (
            "Ouvrez « Applications et fonctionnalités » dans les paramètres "
            "Windows (ou exécutez le désinstalleur dans le dossier "
            "d'installation de Bobine) pour retirer l'application."
        )

    def supports_git_versioning(self) -> bool:
        return False

    def can_auto_apply(self) -> bool:
        return True

    def apply_update(self, target_tag: str | None = None, download_url: str | None = None) -> None:
        if not download_url:
            raise UpdateUnsupported(
                "Aucun lien de téléchargement disponible pour mettre à jour l'application Windows (.exe)."
            )

        import subprocess
        import sys
        import tempfile
        import urllib.request
        from pathlib import Path

        temp_dir = Path(tempfile.gettempdir())
        installer_path = temp_dir / "Bobine-Setup-update.exe"
        logger.info(f"Téléchargement de l'installeur Windows depuis {download_url}...")
        urllib.request.urlretrieve(download_url, installer_path)

        app_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Bobine"
        tray_exe = app_dir / "BobineTray.exe"

        batch_path = temp_dir / "bobine_update_runner.bat"
        # Script batch qui attend la sortie de BobineBackend, exécute l'installeur Inno Setup silencieusement, et relance BobineTray
        batch_content = f"""@echo off
timeout /t 2 /nobreak > NUL
"{installer_path}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS
if exist "{tray_exe}" (
    start "" "{tray_exe}"
)
del "{installer_path}" > NUL 2>&1
del "%~f0" > NUL 2>&1
"""
        batch_path.write_text(batch_content, encoding="latin1")

        logger.info(f"Lancement du batch de mise à jour Windows {batch_path}...")
        creationflags = 0
        if hasattr(subprocess, "DETACHED_PROCESS"):
            creationflags |= subprocess.DETACHED_PROCESS
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(["cmd.exe", "/c", str(batch_path)], creationflags=creationflags, close_fds=True)
        self.restart_services()
