"""Handler du profil `linux-desktop` (app de bureau Linux, paquet .deb).

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
from pathlib import Path
from typing import Callable

from app.utils.deployment import ProfileHandler, UpdateUnsupported
from app.utils.update_orchestrator import download_with_progress, run_checked

logger = logging.getLogger(__name__)

_NOOP_REPORT: Callable[..., None] = lambda *a, **k: None  # noqa: E731


class LinuxDesktopHandler(ProfileHandler):
    profile = "linux-desktop"

    def _backend_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent.parent

    def _repo_root(self) -> Path:
        # `_backend_dir()` (4 niveaux au-dessus de ce fichier) est le dossier
        # `backend/` — utilisable comme `cwd` pour les commandes git
        # (git remonte tout seul jusqu'à la racine du dépôt depuis n'importe
        # quel sous-dossier de l'arbre de travail), mais PAS l'endroit où
        # chercher `.git` lui-même : `.git` vit à la racine du dépôt, UN
        # niveau au-dessus de `backend/`. Confondre les deux (bug corrigé
        # ici) faisait toujours échouer `_is_git_clone()` sur un vrai
        # checkout git de développement, basculant à tort sur le chemin
        # "paquet .deb téléchargé" même en environnement de dev.
        return self._backend_dir().parent

    def _is_git_clone(self) -> bool:
        return (self._repo_root() / ".git").exists()

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
        repo_dir = self._repo_root()
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
        repo_dir = self._backend_dir().parent if self._is_git_clone() else None

        if self._is_git_clone():
            report("checking", message="Récupération de la nouvelle version…")
            if target_tag:
                run_checked(["git", "fetch", "--tags", "--force"], cwd=repo_dir, timeout=45)
                run_checked(["git", "checkout", target_tag], cwd=repo_dir, timeout=45)
                logger.info(f"git checkout {target_tag} (dev linux) effectué avec succès.")
            else:
                run_checked(["git", "pull", "--ff-only"], cwd=repo_dir, timeout=45)
                logger.info("git pull --ff-only (dev linux) effectué avec succès.")
            report("restarting", message="Redémarrage…")
            self.restart_services()
            return

        # Environnement paquet installé .deb
        if not download_url:
            raise UpdateUnsupported(
                "Aucun lien de téléchargement disponible pour mettre à jour le paquet Linux (.deb)."
            )

        deb_file = Path(tempfile.mkdtemp(prefix="bobine-update-")) / "bobine_update.deb"
        report("downloading", percent=0, message="Téléchargement du paquet .deb…")
        download_with_progress(
            download_url, deb_file, asset_digest,
            on_progress=lambda pct: report("downloading", percent=pct, message=f"Téléchargement : {pct}%"),
        )

        # Correctif de la cause racine "l'application ne redémarre jamais
        # après une mise à jour .deb" : l'ANCIEN code lançait `pkexec dpkg -i`
        # en tâche détachée (fire-and-forget, résultat jamais lu) et
        # déléguait la relance à `postinst` du paquet, qui devine
        # l'utilisateur à relancer via la variable d'environnement
        # `$SUDO_USER` — variable que `pkexec` NE positionne JAMAIS
        # (contrairement à `sudo`). Ce process Python tourne DÉJÀ comme
        # l'utilisateur de la session (seule l'installation du paquet exige
        # une élévation via `pkexec`, pas ce process lui-même) : il connaît
        # donc directement qui relancer, sans avoir besoin de deviner quoi
        # que ce soit ni de dépendre de `postinst`. `postinst` reste un
        # filet de sécurité pour le cas d'un `apt upgrade` lancé en dehors
        # de l'application (cf. packaging/linux/DEBIAN/postinst).
        report("installing", message="Installation du paquet (autorisation système requise)…")
        try:
            run_checked(["pkexec", "dpkg", "-i", str(deb_file)], timeout=180)
        except Exception as e:
            raise RuntimeError(f"Échec de l'installation du paquet .deb : {e}") from e
        finally:
            try:
                deb_file.unlink(missing_ok=True)
                deb_file.parent.rmdir()
            except OSError:
                pass

        report("restarting", message="Redémarrage du service…")
        try:
            run_checked(["systemctl", "--user", "restart", "bobine.service"], timeout=20)
        except Exception as e:
            # Le paquet EST installé à ce stade (l'exception précédente
            # aurait déjà interrompu l'exécution sinon) : un échec ICI est
            # signalé clairement plutôt que silencieusement ignoré, mais ne
            # doit pas laisser croire que la mise à jour elle-même a échoué.
            raise RuntimeError(
                f"Paquet installé avec succès, mais le redémarrage automatique du service a échoué "
                f"({e}) — relancez Bobine manuellement pour appliquer la mise à jour."
            ) from e
