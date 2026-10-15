"""Handler du profil `android` (app Chaquopy, voir docs/ARCHITECTURE.md).

Contrairement aux autres profils, il n'existe PAS ici de superviseur léger
(BobineTray, systemd --user) qui relance immédiatement le processus après
`os._exit(0)` : le backend Python tourne intégré au même processus JVM que
`MainActivity`/`BobineForegroundService` (Chaquopy). `START_STICKY`
donne une chance au système de relancer le `Service` après un kill, mais
sans garantie de délai ni de relance de l'UI visible (`MainActivity`) —
contrairement à un simple redémarrage de sous-processus sur desktop. Les
trois appelants de `restart_services()` (réinitialisation complète, restauration
de sauvegarde, remise à zéro d'usine) restent des actions admin délibérées et
rares, jamais déclenchées par un enregistrement de réglage courant — ce choix
reste donc le moins mauvais en l'absence d'un mécanisme de relance dédié.
NON TESTÉ sur matériel réel à ce stade — à valider avant de considérer ce
chemin fiable en production.
"""

import logging
import os
from typing import Callable

from app.utils.deployment import ProfileHandler, UpdateUnsupported

logger = logging.getLogger(__name__)

_NOOP_REPORT: Callable[..., None] = lambda *a, **k: None  # noqa: E731


def _get_android_context():
    """Contexte applicatif Android via Chaquopy.

    `PyApplication` n'expose AUCUN attribut statique `context` (l'ancien code
    levait `type object 'PyApplication' has no attribute 'context'` à chaque
    tentative de mise à jour ou de désinstallation depuis Réglages). La voie
    documentée est `Python.getPlatform().getApplication()` — déjà utilisée par
    `utils/hardware_info.py` et validée sur la tablette pilote."""
    from com.chaquo.python import Python  # Chaquopy
    return Python.getPlatform().getApplication()


class AndroidHandler(ProfileHandler):
    profile = "android"

    # `UpdateManager.downloadAndInstall` télécharge dans un thread JVM et
    # rapporte l'issue par rappel HTTP (`/api/updates/_android-callback`) :
    # `apply_update()` retourne bien avant la fin réelle.
    async_completion = True

    def asset_variant(self) -> str | None:
        """"tv" si l'application tourne sous le flavor Android TV
        (`applicationId` = `com.bobine.app.tv`, cf. build.gradle.kts) —
        l'APK téléphone/tablette installé par-dessus ne la mettrait PAS à
        jour, il installerait une seconde application à côté. Repli sur
        l'APK téléphone en cas d'échec de lecture (jamais bloquant)."""
        try:
            return "tv" if str(_get_android_context().getPackageName()).endswith(".tv") else "mobile"
        except Exception:
            logger.warning("Impossible de lire le nom de paquet Android — APK téléphone/tablette supposé.", exc_info=True)
            return "mobile"

    def restart_services(self) -> None:
        logger.info(
            "Arrêt du process pour redémarrage (Android : relance non garantie, "
            "START_STICKY du ForegroundService seulement)."
        )
        os._exit(0)

    def can_self_uninstall(self) -> bool:
        return True

    def start_uninstall(self) -> None:
        try:
            from java import jclass  # Chaquopy
            Uri = jclass("android.net.Uri")
            Intent = jclass("android.content.Intent")
            context = _get_android_context()
            intent = Intent(Intent.ACTION_DELETE)
            intent.setData(Uri.parse(f"package:{context.getPackageName()}"))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            logger.info("Dialogue système de désinstallation Android ouvert via ACTION_DELETE.")
        except Exception:
            logger.exception("Échec de l'ouverture du dialogue de désinstallation Android")
            raise

    def uninstall_instructions(self) -> str:
        return (
            "Pour désinstaller Bobine, utilisez la gestion des applications d'Android : "
            "appui long sur l'icône Bobine puis Désinstaller, ou Paramètres > Applications > Bobine > Désinstaller."
        )

    def supports_git_versioning(self) -> bool:
        return False

    def can_auto_apply(self) -> bool:
        return True

    def can_schedule_auto_apply(self) -> bool:
        # Le téléchargement/la vérification PEUVENT se déclencher sans
        # supervision (planification quotidienne) — seule l'installation
        # finale exige un tap de confirmation Android (cf. apply_update
        # ci-dessous), décision produit délibérée et maintenue : jamais
        # d'installation silencieuse via PackageInstaller/Device Owner,
        # même si l'appareil dispose des privilèges nécessaires.
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
                "Aucun lien de téléchargement d'APK disponible pour la mise à jour."
            )
        if not asset_digest:
            # Fail-closed, comme `download_with_progress` sur les profils de
            # bureau : un APK jamais vérifié ne doit pas arriver jusqu'au
            # dialogue d'installation (l'ancien chemin Android n'avait aucune
            # vérification d'intégrité).
            raise UpdateUnsupported(
                "Empreinte SHA-256 indisponible pour l'APK — installation annulée par précaution."
            )
        report("downloading", percent=0, message="Téléchargement de l'APK sur l'appareil…")
        try:
            from java import jclass  # Chaquopy
            context = _get_android_context()
            update_mgr = jclass("com.bobine.app.UpdateManager")
            update_mgr.INSTANCE.downloadAndInstall(context, download_url, asset_digest)
        except Exception as exc:
            logger.exception("Échec du déclenchement de la mise à jour Android via UpdateManager")
            raise UpdateUnsupported(f"Impossible de déclencher la mise à jour Android : {exc}") from exc
        # `downloadAndInstall` (Kotlin) lance le téléchargement dans SON
        # PROPRE thread et rend la main immédiatement. La progression, la
        # vérification SHA-256, la validation du paquet (nom, signature,
        # versionCode) et l'étape finale ("en attente de confirmation" /
        # "échec") sont rapportées par le rappel Kotlin ->
        # `POST /api/updates/_android-callback` (cf. routers/updates.py).
        # La confirmation finale nécessitera un tap utilisateur sur la
        # boîte de dialogue système Android (jamais d'installation
        # silencieuse, cf. can_schedule_auto_apply) — et `async_completion`
        # empêche l'orchestrateur de conclure "terminé" à tort ici.
