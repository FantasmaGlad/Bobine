"""Handler du profil `linux-desktop` (app de bureau Linux : .deb, .rpm ou .pkg.tar.zst)."""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from app.utils.deployment import ProfileHandler, UpdateUnsupported
from app.updates.orchestrator import clean_subprocess_env, download_with_progress, run_checked

logger = logging.getLogger(__name__)

_NOOP_REPORT: Callable[..., None] = lambda *a, **k: None  # noqa: E731


def detect_linux_package_format() -> str:
    """Détecte le format de paquet Linux ayant installé Bobine (ou celui natif de la distribution hôte) : `.deb`, `.rpm` ou `.pkg.tar.zst`."""
    env_override = os.environ.get("BOBINE_LINUX_PKG_FORMAT", "").strip().lower()
    if env_override in (".deb", "deb"):
        return ".deb"
    if env_override in (".rpm", "rpm"):
        return ".rpm"
    if env_override in (".pkg.tar.zst", "arch", "pacman"):
        return ".pkg.tar.zst"

    env = clean_subprocess_env()
    for probe_cmd, ext in (
        (["dpkg", "-s", "bobine"], ".deb"),
        (["rpm", "-q", "bobine"], ".rpm"),
        (["pacman", "-Qi", "bobine"], ".pkg.tar.zst"),
    ):
        if shutil.which(probe_cmd[0]):
            try:
                res = subprocess.run(
                    probe_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                    env=env,
                )
                if res.returncode == 0:
                    return ext
            except Exception:
                pass

    if Path("/etc/arch-release").exists():
        return ".pkg.tar.zst"
    if Path("/etc/fedora-release").exists() or Path("/etc/redhat-release").exists():
        return ".rpm"
    if Path("/etc/debian_version").exists():
        return ".deb"

    if shutil.which("pacman") and not shutil.which("dpkg"):
        return ".pkg.tar.zst"
    if (shutil.which("dnf") or shutil.which("rpm")) and not shutil.which("dpkg"):
        return ".rpm"
    return ".deb"


SELF_UPDATE_SENTINEL = "/run/bobine-self-update-in-progress"
_SENTINEL_SCRIPT = f'touch {SELF_UPDATE_SENTINEL}; trap "rm -f {SELF_UPDATE_SENTINEL}" EXIT; "$@"'


def _as_root(command: list[str]) -> list[str]:
    return ["pkexec", "sh", "-c", _SENTINEL_SCRIPT, "sh", *command]


class LinuxDesktopHandler(ProfileHandler):
    profile = "linux-desktop"

    def _backend_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent.parent

    def _repo_root(self) -> Path:
        return self._backend_dir().parent

    def _is_git_clone(self) -> bool:
        return (self._repo_root() / ".git").exists()

    def restart_services(self) -> None:
        logger.info("Déclenchement du redémarrage du service bureau Linux (BobineTray ou systemd --user)...")
        cmd = "sleep 1 && (systemctl --user restart bobine.service || systemctl --user restart bobine || true)"
        try:
            subprocess.Popen(
                ["sh", "-c", cmd], start_new_session=True, env=clean_subprocess_env(),
            )
        except Exception as e:
            logger.debug(f"Relance systemctl --user non disponible : {e}")

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
            pkg_fmt = detect_linux_package_format()
            if pkg_fmt == ".pkg.tar.zst":
                cmd = "sleep 1 && (pkexec pacman -Rns --noconfirm bobine || pkexec pacman -R --noconfirm bobine)"
            elif pkg_fmt == ".rpm":
                cmd = "sleep 1 && (pkexec dnf remove -y bobine || pkexec rpm -e bobine)"
            else:
                cmd = "sleep 1 && (pkexec apt-get remove -y bobine || pkexec dpkg -P bobine || pkexec dpkg -r bobine)"
            subprocess.Popen(["sh", "-c", cmd], start_new_session=True, env=clean_subprocess_env())
        logger.info("Désinstallation Linux desktop déclenchée en tâche de fond via pkexec.")

    def uninstall_instructions(self) -> str:
        pkg_fmt = detect_linux_package_format()
        if pkg_fmt == ".pkg.tar.zst":
            return (
                "Pour désinstaller Bobine manuellement, exécutez dans un terminal : "
                "sudo pacman -Rns bobine."
            )
        if pkg_fmt == ".rpm":
            return (
                "Pour désinstaller Bobine manuellement, exécutez dans un terminal : "
                "sudo dnf remove bobine (ou utilisez votre logithèque habituelle)."
            )
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

        if not download_url:
            raise UpdateUnsupported(
                "Aucun lien de téléchargement disponible pour mettre à jour le paquet Linux."
            )

        url_lower = download_url.lower().split("?", 1)[0]
        if url_lower.endswith(".pkg.tar.zst"):
            pkg_ext = ".pkg.tar.zst"
        elif url_lower.endswith(".rpm"):
            pkg_ext = ".rpm"
        elif url_lower.endswith(".deb"):
            pkg_ext = ".deb"
        else:
            pkg_ext = detect_linux_package_format()

        pkg_file = Path(tempfile.mkdtemp(prefix="bobine-update-")) / f"bobine_update{pkg_ext}"
        report("downloading", percent=0, message=f"Téléchargement du paquet {pkg_ext}…")
        download_with_progress(
            download_url, pkg_file, asset_digest,
            on_progress=lambda pct: report("downloading", percent=pct, message=f"Téléchargement : {pct}%"),
            on_verifying=lambda: report("verifying", message="Vérification de l'intégrité du paquet…"),
        )

        report("installing", message="Installation du paquet (autorisation système requise)…")
        try:
            if pkg_ext == ".pkg.tar.zst":
                run_checked(_as_root(["pacman", "-U", "--noconfirm", str(pkg_file)]), timeout=180)
            elif pkg_ext == ".rpm":
                if shutil.which("dnf"):
                    run_checked(_as_root(["dnf", "install", "-y", str(pkg_file)]), timeout=180)
                else:
                    run_checked(_as_root(["rpm", "-Uvh", "--replacepkgs", str(pkg_file)]), timeout=180)
            elif shutil.which("apt-get"):
                run_checked(_as_root(["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y",
                                      "--allow-downgrades", str(pkg_file)]), timeout=900)
            else:
                run_checked(_as_root(["dpkg", "-i", str(pkg_file)]), timeout=180)
        except Exception as e:
            raise RuntimeError(f"Échec de l'installation du paquet {pkg_ext} : {e}") from e
        finally:
            try:
                pkg_file.unlink(missing_ok=True)
                pkg_file.parent.rmdir()
            except OSError:
                pass

        report("restarting", message="Redémarrage de Bobine…")
        self.restart_services()

