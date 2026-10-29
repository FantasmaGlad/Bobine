"""Handler du profil `macos` (app de bureau macOS, bundle `.app`).

Comme Windows et Linux de bureau : BobineTray supervise BobineBackend en
process enfant, aucun équivalent de service système (launchd géré par
l'utilisateur via LaunchAgent, pas de daemon root). `restart_services()`
se contente de mettre fin au process courant (`os._exit(0)`) : c'est
BobineTray, le superviseur, qui relance le backend. Le LaunchAgent
(`KeepAlive` sur sortie non nulle seulement) ne relance jamais le tray après
cette sortie. Après une mise à jour, ce superviseur est encore le process de
l'ANCIENNE version (seuls les fichiers du bundle ont été remplacés) :
`relaunch_application()` redémarre donc tout le bundle, comme le script de
mise à jour du profil Windows relance BobineTray.exe. La désinstallation est
manuelle (glisser `Bobine.app` vers la Corbeille), comme toute app macOS non
distribuée par le Mac App Store.
"""

import logging
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from app.utils.deployment import ProfileHandler, UpdateUnsupported
from app.utils.update_orchestrator import download_with_progress, run_checked

logger = logging.getLogger(__name__)

_NOOP_REPORT: Callable[..., None] = lambda *a, **k: None  # noqa: E731

_APP_PATH = Path("/Applications/Bobine.app")

# Exécuté par un process détaché : l'ancien tray et l'ancien backend vont
# disparaître, rien d'autre ne peut relancer l'application. Les chemins et PID
# arrivent par l'environnement (jamais dans la ligne de commande) : `pkill -f`
# comparerait sinon le motif à ce script lui-même et le tuerait.
_RELAUNCH_SCRIPT = """#!/bin/sh
# Le backend qui a lancé ce script se termine juste après (os._exit).
n=0
while kill -0 "$BOBINE_BACKEND_PID" 2>/dev/null && [ "$n" -lt 40 ]; do sleep 0.5; n=$((n+1)); done
# Tray d'abord : le superviseur ne relance plus de backend de l'ancienne version.
kill -TERM "$BOBINE_TRAY_PID" 2>/dev/null
pkill -TERM -f "$BOBINE_BACKEND_BIN" 2>/dev/null
n=0
while { kill -0 "$BOBINE_TRAY_PID" 2>/dev/null || pgrep -f "$BOBINE_BACKEND_BIN" >/dev/null 2>&1; } && [ "$n" -lt 20 ]; do
    sleep 0.5; n=$((n+1))
done
kill -KILL "$BOBINE_TRAY_PID" 2>/dev/null
pkill -KILL -f "$BOBINE_BACKEND_BIN" 2>/dev/null
open "$BOBINE_APP"
rm -f "$0"
"""


def _is_bobine_tray(pid: int) -> bool:
    """Le parent du backend est-il bien BobineTray ? Hors bundle (développement,
    uvicorn lancé à la main), le parent est un shell qu'il ne faut pas tuer."""
    try:
        res = subprocess.run(
            ["ps", "-o", "comm=", "-p", str(pid)], capture_output=True, text=True, timeout=5, check=True
        )
    except Exception:
        return False
    return Path(res.stdout.strip()).name == "BobineTray"


class MacOSHandler(ProfileHandler):
    profile = "macos"

    def restart_services(self) -> None:
        logger.info("Arrêt du process pour redémarrage (relance attendue de BobineTray/LaunchAgent).")
        # Sortie immédiate après l'envoi de la réponse HTTP de reset / mise à jour
        os._exit(0)

    def relaunch_application(self) -> None:
        """Redémarre tout le bundle (tray + backend) depuis les fichiers
        fraîchement installés ; repli sur `restart_services()` (le tray relance
        alors le seul backend) quand le tray parent est introuvable ou que le
        script ne peut pas être lancé."""
        tray_pid = os.getppid()
        if not _is_bobine_tray(tray_pid):
            logger.warning("Parent du backend différent de BobineTray : relance du seul backend.")
            self.restart_services()
            return
        try:
            script_path = Path(tempfile.gettempdir()) / "bobine_relaunch_runner.sh"
            script_path.write_text(_RELAUNCH_SCRIPT, encoding="utf-8")
            script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)
            subprocess.Popen(
                ["sh", str(script_path)],
                env={
                    **os.environ,
                    "BOBINE_APP": str(_APP_PATH),
                    "BOBINE_BACKEND_BIN": str(_APP_PATH / "Contents" / "MacOS" / "BobineBackend"),
                    "BOBINE_TRAY_PID": str(tray_pid),
                    "BOBINE_BACKEND_PID": str(os.getpid()),
                },
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True, close_fds=True,
            )
        except Exception:
            logger.exception("Script de relance macOS impossible à lancer : relance du seul backend.")
        self.restart_services()

    def can_self_uninstall(self) -> bool:
        return True

    def start_uninstall(self) -> None:
        cmd = (
            "sleep 1 && "
            "rm -f ~/Library/LaunchAgents/com.bobine.app.plist && "
            "rm -rf /Applications/Bobine.app"
        )
        subprocess.Popen(["sh", "-c", cmd], start_new_session=True)
        os._exit(0)

    def uninstall_instructions(self) -> str:
        return (
            "Quittez Bobine (icône de la barre de menus > Quitter), faites glisser "
            "Bobine.app depuis le dossier Applications vers la Corbeille, puis supprimez "
            "~/Library/LaunchAgents/com.bobine.app.plist pour désactiver le lancement automatique."
        )

    def supports_git_versioning(self) -> bool:
        return False

    def can_auto_apply(self) -> bool:
        return True

    def can_schedule_auto_apply(self) -> bool:
        # Code neuf, jamais exécuté sur une vraie machine macOS (aucune CI
        # macOS pour ce chemin à ce jour) — reste éligible au bouton manuel
        # (`can_auto_apply`) mais volontairement exclu du déclenchement
        # planifié sans supervision tant qu'un premier passage manuel n'a
        # pas été validé sur du matériel réel.
        return False

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
                "Aucun lien de téléchargement disponible pour mettre à jour l'application macOS (.dmg)."
            )

        dmg_path = Path(tempfile.gettempdir()) / "Bobine-update.dmg"
        report("downloading", percent=0, message="Téléchargement de l'image disque…")
        download_with_progress(
            download_url, dmg_path, asset_digest,
            on_progress=lambda pct: report("downloading", percent=pct, message=f"Téléchargement : {pct}%"),
            on_verifying=lambda: report("verifying", message="Vérification de l'intégrité de l'image disque…"),
        )

        report("installing", message="Montage de l'image disque…")
        mount_point: str | None = None
        try:
            mount_res = run_checked(
                ["hdiutil", "attach", "-nobrowse", "-plist", str(dmg_path)], timeout=60
            )
            # Sortie `-plist` volontairement non parsée en XML complet (pas
            # de dépendance plist supplémentaire ici) : le point de montage
            # ("/Volumes/...") est la seule ligne <string> qui commence par
            # ce préfixe dans la sortie hdiutil — suffisant et robuste en
            # pratique pour un usage interne, pas un fichier plist arbitraire
            # dont il faudrait gérer toute la richesse du format.
            for line in mount_res.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("<string>/Volumes/"):
                    mount_point = stripped.removeprefix("<string>").removesuffix("</string>")
                    break
            if not mount_point:
                raise RuntimeError("Point de montage introuvable dans la sortie de hdiutil.")

            source_app = Path(mount_point) / "Bobine.app"
            if not source_app.exists():
                raise RuntimeError(f"Bobine.app introuvable dans l'image montée ({mount_point}).")

            report("installing", message="Remplacement de l'application…")
            # `rsync -a --delete` plutôt qu'un simple `cp -R` : préserve les
            # attributs du bundle et garantit qu'aucun fichier de l'ancienne
            # version (retiré depuis) ne survit dans le nouveau bundle. Le
            # LaunchAgent (cf. tray.py::_ensure_launch_agent_macos) cible le
            # CHEMIN du bundle (/Applications/Bobine.app), jamais un binaire
            # versionné — remplacer le contenu en place suffit, aucune
            # réinstallation du LaunchAgent n'est nécessaire ici.
            run_checked(
                ["rsync", "-a", "--delete", f"{source_app}/", f"{_APP_PATH}/"], timeout=120
            )
        finally:
            if mount_point:
                try:
                    run_checked(["hdiutil", "detach", mount_point, "-quiet"], timeout=30)
                except Exception as e:
                    logger.warning(f"Échec du démontage de l'image disque ({mount_point}) : {e}")
            try:
                dmg_path.unlink(missing_ok=True)
            except OSError:
                pass

        report("restarting", message="Redémarrage…")
        self.relaunch_application()
