"""Handler du profil `android` (app Chaquopy, cf. CDC docs/PortabiliteAndroid.md,
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
        return False

    def uninstall_instructions(self) -> str:
        return (
            "Pour désinstaller Bobine, utilisez la gestion des applications d'Android : "
            "appui long sur l'icône Bobine puis Désinstaller, ou Paramètres > Applications > Bobine > Désinstaller."
        )

    def supports_git_versioning(self) -> bool:
        return False

    def apply_update(self, target_tag: str | None = None) -> None:
        raise UpdateUnsupported(
            "La mise à jour automatique n'est pas encore disponible sur Android — "
            "réinstallez le dernier APK depuis les releases GitHub du projet "
            "(github.com/FantasmaGlad/Bobine/releases)."
        )
