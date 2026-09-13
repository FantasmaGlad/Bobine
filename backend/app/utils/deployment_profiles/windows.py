"""Handler du profil `windows` (app de bureau, .exe PyInstaller +
installeur Inno Setup).

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
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from app.utils.deployment import ProfileHandler, UpdateUnsupported
from app.utils.update_orchestrator import download_with_progress, status_file_path

logger = logging.getLogger(__name__)

_NOOP_REPORT: Callable[..., None] = lambda *a, **k: None  # noqa: E731


def _detached_creationflags() -> int:
    flags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags |= subprocess.DETACHED_PROCESS
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    return flags


def _app_dir() -> Path:
    return (
        Path(sys.executable).parent
        if getattr(sys, "frozen", False)
        else Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Bobine"
    )


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
        app_dir = _app_dir()
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
        subprocess.Popen(
            ["cmd.exe", "/c", str(batch_path)],
            creationflags=_detached_creationflags(), close_fds=True,
        )
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
        if not download_url:
            raise UpdateUnsupported(
                "Aucun lien de téléchargement disponible pour mettre à jour l'application Windows (.exe)."
            )

        temp_dir = Path(tempfile.gettempdir())
        installer_path = temp_dir / "Bobine-Setup-update.exe"
        report("downloading", percent=0, message="Téléchargement de l'installeur…")
        logger.info(f"Téléchargement de l'installeur Windows depuis {download_url}...")
        download_with_progress(
            download_url, installer_path, asset_digest,
            on_progress=lambda pct: report("downloading", percent=pct, message=f"Téléchargement : {pct}%"),
        )

        tray_exe = _app_dir() / "BobineTray.exe"
        # Ce process va se terminer (`self.restart_services()` en fin de
        # méthode) AVANT que l'installeur Inno Setup n'ait fini de
        # remplacer les fichiers verrouillés par le process courant — le
        # script de relance doit donc s'exécuter dans un process
        # totalement détaché, qui écrit lui-même l'issue finale dans le
        # fichier d'état (`status_file_path()`), relu par le PROCHAIN
        # démarrage du backend (cf. `load_persisted_state_at_startup`).
        # PowerShell plutôt qu'un script .bat classique (ancien code) :
        # code de sortie de l'installeur enfin vérifié (`$proc.ExitCode`,
        # jamais lu auparavant — un échec silencieux d'installation
        # relançait quand même l'ancien BobineTray sans que personne ne le
        # sache), et écriture JSON fiable via `ConvertTo-Json` là où
        # échapper des guillemets dans un `echo` batch est notoirement
        # fragile.
        ps_script_path = temp_dir / "bobine_update_runner.ps1"
        status_path = status_file_path()
        status_path.parent.mkdir(parents=True, exist_ok=True)
        ps_script = f"""
Start-Sleep -Seconds 2
$installer = "{installer_path}"
$tray = "{tray_exe}"
$statusFile = "{status_path}"

function Write-Status($step, $message, $error) {{
    $result = [ordered]@{{
        step = $step
        percent = $(if ($step -eq "done") {{ 100 }} else {{ $null }})
        message = $message
        error = $error
        updated_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    }}
    $result | ConvertTo-Json | Set-Content -Path $statusFile -Encoding utf8
}}

$proc = Start-Process -FilePath $installer -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART","/CLOSEAPPLICATIONS" -Wait -PassThru
$exitCode = $proc.ExitCode
Remove-Item -Path $installer -ErrorAction SilentlyContinue

if ($exitCode -ne 0) {{
    Write-Status "failed" "Installation Windows echouee (code $exitCode)." "install_exit_code_$exitCode"
    Remove-Item -Path $MyInvocation.MyCommand.Path -ErrorAction SilentlyContinue
    exit $exitCode
}}

# Jusqu'a 5 tentatives espacees de 3s : un antivirus qui scanne encore les
# fichiers fraichement installes, ou un verrou de fichier qui se libere
# avec un leger retard, ne doivent pas etre traites comme un echec
# definitif des la premiere tentative (ancien comportement : un seul
# `if exist` immediat, sans retry).
$launched = $false
for ($i = 0; $i -lt 5; $i++) {{
    if (Test-Path $tray) {{
        Start-Process -FilePath $tray
        $launched = $true
        break
    }}
    Start-Sleep -Seconds 3
}}

if ($launched) {{
    Write-Status "done" "Mise a jour installee et application relancee avec succes." $null
}} else {{
    Write-Status "failed" "Installation reussie mais BobineTray.exe introuvable pour la relance automatique." "tray_not_found"
}}
Remove-Item -Path $MyInvocation.MyCommand.Path -ErrorAction SilentlyContinue
"""
        ps_script_path.write_text(ps_script, encoding="utf-8")

        report("installing", message="Installation en cours (l'application va redémarrer)…")
        logger.info(f"Lancement du runner PowerShell de mise à jour {ps_script_path}...")
        subprocess.Popen(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden", "-File", str(ps_script_path),
            ],
            creationflags=_detached_creationflags(), close_fds=True,
        )

        report("restarting", message="Redémarrage…")
        self.restart_services()
