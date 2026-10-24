"""Détection du profil de déploiement et comportement système qui en
dépend — redémarrage des services, désinstallation, mise à jour.

Un seul point d'entrée (`get_profile_handler()`) pour que
`routers/settings.py` et `routers/updates.py` n'appellent plus jamais
`sudo`/`systemctl`/`git` directement selon la plateforme : chaque profil
ajoute son propre fichier de handler dans `deployment_profiles/`, sans
jamais toucher aux deux routers ni à ce module — voir `docs/ARCHITECTURE.md`
pour le détail des cinq profils cibles.
"""

import platform
from pathlib import Path
from typing import Callable, Literal

from app import release_channel
from app.utils.android_runtime import is_android

DeploymentProfile = Literal["linux-headless", "linux-desktop", "windows", "macos", "android"]

# Artefacts posés par install.sh sur l'appliance headless : leur présence est ce qui distingue un
# Linux headless (appliance) d'un Linux de bureau —
# les deux tournant par ailleurs sous le même OS.
UNINSTALL_WRAPPER = Path("/usr/local/sbin/bobine-uninstall")
SUDOERS_FILE = Path("/etc/sudoers.d/bobine")

# Noms des unités systemd de l'appliance headless — utilisés par le handler
# linux-headless, gardés ici pour rester l'unique source de vérité (au lieu
# d'être dupliqués dans settings.py ET updates.py comme avant ce lot).
BACKEND_SERVICE_UNIT = "bobine-backend.service"
KIOSK_SERVICE_UNIT = "bobine-kiosk.service"


def get_deployment_profile() -> DeploymentProfile:
    """Détecte le profil de déploiement de la machine courante.

    Windows/macOS sont déterminés directement par l'OS. Sous Linux, seule
    la présence des artefacts d'`install.sh` distingue l'appliance headless
    du profil de bureau — les deux sont le même OS.
    """
    # Android d'abord : Chaquopy 3.12+ répond "Android" à platform.system(),
    # mais son runtime 3.11 (flavor TV, armeabi-v7a) répond "Linux" — sans ce
    # test indépendant de la version, le profil retomberait sur
    # "linux-desktop" (cf. android.py pour les comportements qui divergent :
    # redémarrage, désinstallation, mise à jour APK).
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
    """Levée par un `ProfileHandler` qui ne sait pas encore appliquer de
    mise à jour automatique sur son profil."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ProfileHandler:
    """Interface commune — une sous-classe concrète par profil, dans
    `deployment_profiles/`. Ne pas instancier directement."""

    profile: DeploymentProfile

    # True si `apply_update()` retourne AVANT l'issue réelle de la mise à
    # jour (travail délégué à un autre thread/process qui la rapportera lui-
    # même) — l'orchestrateur ne doit alors jamais conclure "terminé" au
    # retour de la méthode. Aujourd'hui : Android seulement.
    async_completion: bool = False

    def asset_variant(self) -> str | None:
        """Variante de l'asset de release à choisir quand une même release
        en publie plusieurs pour ce profil (Android : APK téléphone/tablette
        vs APK Android TV, deux `applicationId` distincts — installer le
        mauvais ne met PAS à jour l'application en place, il en installe une
        seconde à côté). None = aucune ambiguïté."""
        return None

    def restart_services(self) -> None:
        """Redémarre le backend (et le kiosque, le cas échéant) — utilisé
        à la fois par le bouton Réinitialiser et après une mise à jour."""
        raise NotImplementedError

    def can_self_uninstall(self) -> bool:
        """True si `start_uninstall()` peut réellement déclencher la
        désinstallation depuis le backend lui-même. False si ce profil
        doit se contenter d'afficher des instructions (cf.
        `uninstall_instructions()`)."""
        return False

    def start_uninstall(self) -> None:
        raise NotImplementedError

    def uninstall_instructions(self) -> str:
        """Message affiché à la place du bouton d'action directe, pour un
        profil où la désinstallation automatique n'est pas sûre (pas d'équivalent fiable à l'enveloppe
        systemd-run de l'appliance headless)."""
        raise NotImplementedError

    def supports_git_versioning(self) -> bool:
        """True uniquement pour l'appliance headless (seul profil dont le
        dossier d'installation est un vrai checkout git, posé par
        `install.sh`). Évite d'exécuter `git rev-parse`/`git describe` en
        pure perte sur les profils packagés (`.exe`, `.app`, `.deb`), qui
        échoueraient silencieusement à chaque appel."""
        return False

    def is_store_managed(self) -> bool:
        """True quand l'application vient d'une boutique (Google Play) : les mises à jour
        passent alors par la boutique, jamais par la mise à jour intégrée."""
        return False

    def store_update_status(self) -> dict:
        """État de la mise à jour proposée par la boutique (`state` : none, available, downloading,
        downloaded, installing, failed, unavailable). Profils sans boutique : « unavailable »."""
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

    def can_auto_apply(self) -> bool:
        """True si ce profil permet l'application automatique d'une mise à jour."""
        return self.supports_git_versioning()

    def can_schedule_auto_apply(self) -> bool:
        """True si ce profil peut être déclenché SANS surveillance humaine
        par la planification quotidienne (Réglages → Mise à jour
        automatique). Volontairement plus restrictif que `can_auto_apply()`
        (qui autorise déjà le bouton manuel) le temps qu'un profil soit
        validé en conditions réelles : un profil récemment automatisé mais
        jamais testé sur du matériel réel (macOS) ne doit pas pouvoir se
        déclencher tout seul à 3h du matin sans supervision. Redéfini à
        True dans chaque handler une fois ce profil éprouvé."""
        return False

    def apply_update(
        self,
        target_tag: str | None = None,
        download_url: str | None = None,
        asset_digest: str | None = None,
        report: "Callable[..., None] | None" = None,
    ) -> None:
        """Applique la mise à jour (typiquement `git checkout <tag>` ou
        téléchargement d'installeur + redémarrage). `target_tag` permet de
        cibler explicitement un tag. `download_url`/`asset_digest` sont
        l'URL et l'empreinte SHA-256 (`sha256:<hex>`, déjà fournie par
        l'API GitHub Releases) de l'asset pour les profils non-git.

        `report(step, percent=None, message=None)` — si fourni par
        l'appelant (`update_orchestrator.run_update_pipeline`) — est une
        fonction SYNCHRONE à appeler à chaque étape significative
        (téléchargement, vérification, installation, redémarrage) pour
        que la progression soit diffusée en temps réel. Cette méthode
        s'exécute déjà hors de la boucle asyncio (`asyncio.to_thread`
        côté appelant) : les appels bloquants (subprocess, téléchargement)
        y sont donc sans risque pour `/api/health`."""
        raise UpdateUnsupported(
            "La mise à jour automatique n'est pas encore disponible sur ce "
            "profil — téléchargez la dernière version depuis les releases "
            "GitHub du projet (github.com/FantasmaGlad/Bobine/releases)."
        )


_handler: ProfileHandler | None = None


def get_profile_handler() -> ProfileHandler:
    """Handler pour le profil de LA machine courante, mis en cache (le
    profil ne change jamais en cours d'exécution)."""
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
    """Canal effectif de CETTE installation (cf. release_channel.resolve), point d'entrée unique des
    réglages et des mises à jour. Un build distribué par une boutique (Google Play) est verrouillé
    sur la Stable : il ne se met à jour que par la boutique, qui ne publie que la Stable, et son
    icône reste celle de la Stable quel que soit le réglage (restauré d'une sauvegarde, par exemple)."""
    locked = release_channel.DEFAULT_CHANNEL if get_profile_handler().is_store_managed() else None
    return release_channel.resolve(stored, locked=locked)
