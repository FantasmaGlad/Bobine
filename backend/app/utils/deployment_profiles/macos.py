"""Handler du profil `macos` (app de bureau macOS, bundle `.app`).

Comme Windows et Linux de bureau : BobineTray supervise BobineBackend en
process enfant, aucun équivalent de service système (launchd géré par
l'utilisateur via LaunchAgent, pas de daemon root). `restart_services()`
se contente de mettre fin au process courant (`os._exit(0)`) : c'est
BobineTray (relancé lui-même par launchd si le LaunchAgent a `KeepAlive`
actif) qui le relance. La désinstallation est manuelle (glisser
`Bobine.app` vers la Corbeille), comme toute app macOS non distribuée par
le Mac App Store.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from app.utils.deployment import ProfileHandler, UpdateUnsupported
from app.utils.update_orchestrator import download_with_progress, run_checked

logger = logging.getLogger(__name__)

_NOOP_REPORT: Callable[..., None] = lambda *a, **k: None  # noqa: E731

_APP_PATH = Path("/Applications/Bobine.app")


class MacOSHandler(ProfileHandler):
    profile = "macos"

    def restart_services(self) -> None:
        logger.info("Arrêt du process pour redémarrage (relance attendue de BobineTray/LaunchAgent).")
        # Sortie immédiate après l'envoi de la réponse HTTP de reset / mise à jour
        os._exit(0)

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
        self.restart_services()
