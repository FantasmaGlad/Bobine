"""Handler du profil `android` (app Chaquopy, cf. CDC docs/ARCHITECTURE.md,
plan docs/plan-implementation-android.md Lot 12).

Contrairement aux autres profils, il n'existe PAS ici de superviseur léger
(BobineTray, systemd --user) qui relance immédiatement le processus après
`os._exit(0)` : le backend Python tourne intégré au même processus JVM que
`MainActivity`/`BobineForegroundService` (Chaquopy). `START_STICKY` (Lot 6)
donne une chance au système de relancer le `Service` après un kill, mais
sans garantie de délai ni de relance de l'UI visible (`MainActivity`) —
contrairement à un simple redémarrage de sous-processus sur desktop. Les
trois appelants de `restart_services()` (réinitialisation complète, restauration
de sauvegarde, remise à zéro d'usine) restent des actions admin délibérées et
rares, jamais déclenchées par un enregistrement de réglage courant — ce choix
reste donc le moins mauvais en l'absence d'un mécanisme de relance dédié
(Lot 10 : Device Owner/exemption batterie serait l'endroit naturel pour
fiabiliser ça, ex. relance programmée via AlarmManager avant la sortie).
NON TESTÉ sur matériel réel à ce stade — à valider avant de considérer ce
chemin fiable en production.
"""

import logging
import os

from app.utils.deployment import ProfileHandler, UpdateUnsupported

logger = logging.getLogger(__name__)


class AndroidHandler(ProfileHandler):
    profile = "android"

    def restart_services(self) -> None:
        logger.info(
            "Arrêt du process pour redémarrage (Android : relance non garantie, "
            "START_STICKY du ForegroundService seulement — voir Lot 10)."
        )
        os._exit(0)

    def can_self_uninstall(self) -> bool:
        return True

    def start_uninstall(self) -> None:
        try:
            from java import jclass  # Chaquopy
            Uri = jclass("android.net.Uri")
            Intent = jclass("android.content.Intent")
            py_app = jclass("com.chaquo.python.android.PyApplication")
            context = py_app.context
            intent = Intent(Intent.ACTION_DELETE)
            intent.setData(Uri.parse("package:com.bobine.app"))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            logger.info("Dialogue système de désinstallation Android ouvert via ACTION_DELETE.")
        except Exception as exc:
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

    def apply_update(self, target_tag: str | None = None, download_url: str | None = None) -> None:
        if not download_url:
            raise UpdateUnsupported(
                "Aucun lien de téléchargement d'APK disponible pour la mise à jour."
            )
        try:
            from java import jclass  # Chaquopy
            py_app = jclass("com.chaquo.python.android.PyApplication")
            context = py_app.context
            update_mgr = jclass("com.bobine.app.UpdateManager")
            update_mgr.INSTANCE.downloadAndInstall(context, download_url)
        except Exception as exc:
            logger.exception("Échec du déclenchement de la mise à jour Android via UpdateManager")
            raise UpdateUnsupported(f"Impossible de déclencher la mise à jour Android : {exc}") from exc
