"""Détection du profil de déploiement et comportement système qui en dépend — redémarrage des services, désinstallation, mise à jour."""

import platform
from pathlib import Path
from typing import Callable, Literal

from app import release_channel
from app.utils.android_runtime import is_android

DeploymentProfile = Literal["linux-headless", "linux-desktop", "windows", "macos", "android"]

UNINSTALL_WRAPPER = Path("/usr/local/sbin/bobine-uninstall")
SUDOERS_FILE = Path("/etc/sudoers.d/bobine")

BACKEND_SERVICE_UNIT = "bobine-backend.service"
KIOSK_SERVICE_UNIT = "bobine-kiosk.service"


def get_deployment_profile() -> DeploymentProfile:
    """Détecte le profil de déploiement de la machine courante."""
    if is_android():
        return "android"
    system = platform.system()
    if system == "Windows":
        return "windows"
    if system == "Darwin":
        return "macos"
    if UNINSTALL_WRAPPER.exists() and SUDOERS_FILE.exists():
        return "linux-headless"
    return "linux-desktop"


class UpdateUnsupported(Exception):
    """Levée par un `ProfileHandler` qui ne sait pas encore appliquer de mise à jour automatique sur son profil."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ProfileHandler:
    """Interface commune — une sous-classe concrète par profil, dans `deployment_profiles/`."""

    profile: DeploymentProfile

    async_completion: bool = False

    def asset_variant(self) -> str | None:
        """Variante de l'asset de release à choisir quand une même release en publie plusieurs pour ce profil (Android : APK téléphone/tablette vs APK Android TV, deux `applicationId` distincts — installer le mauvais ne met PAS à jour l'application en place, il en installe une seconde à côté)."""
        return None

    def restart_services(self) -> None:
        """Redémarre le backend (et le kiosque, le cas échéant) — utilisé à la fois par le bouton Réinitialiser et après une mise à jour."""
        raise NotImplementedError

    def restart_is_guaranteed(self) -> bool:
        """Vrai si un superviseur (systemd, BobineTray, LaunchAgent) relance le backend après `restart_services()`."""
        return True

    def can_self_uninstall(self) -> bool:
        """True si `start_uninstall()` peut réellement déclencher la désinstallation depuis le backend lui-même."""
        return False

    def start_uninstall(self) -> None:
        raise NotImplementedError

    def uninstall_instructions(self) -> str:
        """Message affiché à la place du bouton d'action directe, pour un profil où la désinstallation automatique n'est pas sûre (pas d'équivalent fiable à l'enveloppe systemd-run de l'appliance headless)."""
        raise NotImplementedError

    def supports_git_versioning(self) -> bool:
        """True uniquement pour l'appliance headless (seul profil dont le dossier d'installation est un vrai checkout git, posé par `install.sh`)."""
        return False

    def is_store_managed(self) -> bool:
        """True quand l'application vient d'une boutique (Google Play) : les mises à jour passent alors par la boutique, jamais par la mise à jour intégrée."""
        return False

    def store_update_status(self) -> dict:
        """État de la mise à jour proposée par la boutique (`state` : none, available, downloading, downloaded, installing, failed, unavailable)."""
        return {"state": "unavailable"}

    def store_update_start(self) -> dict:
        """Lance la mise à jour via la boutique (interface de la boutique, jamais un APK téléchargé par Bobine)."""
        raise UpdateUnsupported("Aucune boutique n'est associée à cette installation.")

    def store_update_complete(self) -> dict:
        """Installe une mise à jour déjà téléchargée par la boutique."""
        raise UpdateUnsupported("Aucune boutique n'est associée à cette installation.")

    def store_open_listing(self) -> dict:
        """Ouvre la fiche de l'application dans la boutique."""
        raise UpdateUnsupported("Aucune boutique n'est associée à cette installation.")

    def has_system_port80_redirect(self) -> bool:
        """True si le système redirige déjà le port 80 vers Bobine (règle nftables de l'appliance, `install.sh`)."""
        return False

    def tries_port80_redirect(self) -> bool:
        """True si Bobine peut tenter d'écouter lui-même le port 80 pour rediriger (postes de bureau ; jamais sur l'appliance, déjà redirigée par le système, ni sur Android, où les ports inférieurs à 1024 sont interdits)."""
        return not self.has_system_port80_redirect()

    def supports_update_over_tor(self) -> bool:
        """True si TOUT le trafic d'une mise à jour peut passer par Tor (recherche et téléchargement par `tor_proxy`)."""
        return not self.is_store_managed()

    def can_auto_apply(self) -> bool:
        """True si ce profil permet l'application automatique d'une mise à jour."""
        return self.supports_git_versioning()

    def can_schedule_auto_apply(self) -> bool:
        """True si ce profil peut être déclenché SANS surveillance humaine par la planification quotidienne (Réglages → Mise à jour automatique)."""
        return False

    def apply_update(
        self,
        target_tag: str | None = None,
        download_url: str | None = None,
        asset_digest: str | None = None,
        report: "Callable[..., None] | None" = None,
    ) -> None:
        """Applique la mise à jour (typiquement `git checkout <tag>` ou téléchargement d'installeur + redémarrage)."""
        raise UpdateUnsupported(
            "La mise à jour automatique n'est pas encore disponible sur ce "
            "profil — téléchargez la dernière version depuis les releases "
            "GitHub du projet (github.com/FantasmaGlad/Bobine/releases)."
        )


_handler: ProfileHandler | None = None


def get_profile_handler() -> ProfileHandler:
    """Handler pour le profil de LA machine courante, mis en cache (le profil ne change jamais en cours d'exécution)."""
    global _handler
    if _handler is None:
        profile = get_deployment_profile()
        if profile == "windows":
            from app.utils.deployment_profiles.windows import WindowsHandler
            _handler = WindowsHandler()
        elif profile == "linux-desktop":
            from app.utils.deployment_profiles.linux_desktop import LinuxDesktopHandler
            _handler = LinuxDesktopHandler()
        elif profile == "macos":
            from app.utils.deployment_profiles.macos import MacOSHandler
            _handler = MacOSHandler()
        elif profile == "android":
            from app.utils.deployment_profiles.android import AndroidHandler
            _handler = AndroidHandler()
        else:
            from app.utils.deployment_profiles.linux_headless import LinuxHeadlessHandler
            _handler = LinuxHeadlessHandler()
    return _handler


def resolve_update_channel(stored: object) -> release_channel.ChannelChoice:
    """Canal effectif de CETTE installation (cf."""
    locked = release_channel.DEFAULT_CHANNEL if get_profile_handler().is_store_managed() else None
    return release_channel.resolve(stored, locked=locked)
