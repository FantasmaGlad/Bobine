"""Détection du profil de déploiement et comportement système qui en
dépend — redémarrage des services, désinstallation, mise à jour.

Un seul point d'entrée (`get_profile_handler()`) pour que
`routers/settings.py` et `routers/updates.py` n'appellent plus jamais
`sudo`/`systemctl`/`git` directement selon la plateforme : chaque profil
ajoute son propre fichier de handler dans `deployment_profiles/`, sans
jamais toucher aux deux routers ni à ce module — voir `docs/ARCHITECTURE.md`
§4 pour le détail des cinq profils cibles.
"""

import platform
from pathlib import Path
from typing import Callable, Literal

DeploymentProfile = Literal["linux-headless", "linux-desktop", "windows", "macos", "android"]

# Artefacts posés par install.sh sur l'appliance headless (réf.
# install.sh:1266-1294, 917-920) : leur présence est ce qui distingue un
# Linux headless (appliance) d'un Linux de bureau (Lot 2, paquet .deb) —
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
    system = platform.system()
    if system == "Windows":
        return "windows"
    if system == "Darwin":
        return "macos"
    # Chaquopy (cf. docs/plan-implementation-android.md, Découvertes du
    # Lot 7) : platform.system() renvoie bien "Android", pas "Linux", bien
    # que le noyau sous-jacent en soit un - un test explicite est donc
    # nécessaire ici, sans quoi ce cas tomberait dans le repli
    # "linux-desktop" plus bas (fonctionnellement presque correct par
    # accident jusqu'ici, mais fragile pour tout comportement futur qui
    # devrait diverger, ex. redémarrage/désinstallation - cf. android.py).
    if system == "Android":
        return "android"
    if UNINSTALL_WRAPPER.exists() and SUDOERS_FILE.exists():
        return "linux-headless"
    return "linux-desktop"


class UpdateUnsupported(Exception):
    """Levée par un `ProfileHandler` qui ne sait pas encore appliquer de
    mise à jour automatique sur son profil (cf. CDC §12 : mécanisme non
    cadré pour les profils desktop à ce stade)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ProfileHandler:
    """Interface commune — une sous-classe concrète par profil, dans
    `deployment_profiles/`. Ne pas instancier directement."""

    profile: DeploymentProfile

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
        profil où la désinstallation automatique n'est pas sûre (§5.3 du
        plan — pas d'équivalent fiable à l'enveloppe systemd-run de
        l'appliance headless)."""
        raise NotImplementedError

    def supports_git_versioning(self) -> bool:
        """True uniquement pour l'appliance headless (seul profil dont le
        dossier d'installation est un vrai checkout git, posé par
        `install.sh`). Évite d'exécuter `git rev-parse`/`git describe` en
        pure perte sur les profils packagés (`.exe`, `.app`, `.deb`), qui
        échoueraient silencieusement à chaque appel."""
        return False

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
