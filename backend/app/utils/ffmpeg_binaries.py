"""Résolution du binaire ffmpeg/ffprobe à invoquer (Lot 8, cf.
docs/plan-implementation-android.md).

Nom nu (`"ffmpeg"`/`"ffprobe"`, résolu via `PATH`) sur toutes les
plateformes existantes — comportement inchangé. Sous Android, Android 10+
interdit d'exécuter un binaire natif depuis ailleurs que le dossier natif
de l'app (contrainte W^X) : `android/app/src/main/java/com/bobine/app/
BobineForegroundService.kt` transmet `context.applicationInfo.nativeLibraryDir`
à `bobine_bootstrap.start_server_once()`, qui pose
`BOBINE_FFMPEG_BIN`/`BOBINE_FFPROBE_BIN` (chemins absolus vers les
binaires statiques ARM64 embarqués en `lib*.so`, cf. Découvertes du Lot 8)
avant le premier import de ce module.

Résolu une seule fois au chargement du module, pas à chaque appel.
"""

import os

FFMPEG_BIN = os.environ.get("BOBINE_FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.environ.get("BOBINE_FFPROBE_BIN", "ffprobe")
