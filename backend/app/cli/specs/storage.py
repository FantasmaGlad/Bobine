from __future__ import annotations

from app.api.contract import MOUNT_MODES, STORAGE_IMPORT_KINDS

from .model import Spec
from .route import route

_VOLUME = "/api/storage/volumes/{key}"
_KIND = "kind=" + "|".join(STORAGE_IMPORT_KINDS)
_OPTIONS = ("read_only:bool", "noatime:bool", "noexec:bool", "standby_minutes:int", "smart_monitor:bool", "auto_mount_library:bool")

SPECS: tuple[Spec, ...] = (
    route("storage", "mount", "POST", f"{_VOLUME}/mount", "monter un support", body=("mode=" + "|".join(MOUNT_MODES),)),
    route("storage", "unmount", "POST", f"{_VOLUME}/unmount", "démonter un support"),
    route("storage", "eject", "POST", f"{_VOLUME}/eject", "éjecter un support"),
    route("storage", "health", "GET", f"{_VOLUME}/health", "santé d'un support", query=("refresh:bool",)),
    route("storage", "trim", "POST", f"{_VOLUME}/trim", "libérer les blocs inutilisés (TRIM)"),
    route("storage", "volume-set", "PUT", f"{_VOLUME}/settings", "options d'un support", body=_OPTIONS, require_one=True),
    route("storage", "defaults-set", "PUT", "/api/storage/settings", "options par défaut des supports", body=_OPTIONS, require_one=True),
    route("storage", "import", "POST", f"{_VOLUME}/import", "copier des fichiers du support dans la bibliothèque",
          body=(_KIND, "entries:json", "force:bool"), pos=("kind", "entries")),
    route("storage", "index", "POST", f"{_VOLUME}/index", "indexer des fichiers sans les copier",
          body=(_KIND, "entries:json", "force:bool"), pos=("kind", "entries")),
    route("storage", "export", "POST", f"{_VOLUME}/export", "copier des médias vers le support",
          body=("kind", "ids:ints", "dest"), pos=("kind", "ids")),
    route("storage", "library", "POST", f"{_VOLUME}/library", "déclarer le support comme bibliothèque", body=("nickname",)),
    route("storage", "library-rm", "DELETE", f"{_VOLUME}/library", "retirer la bibliothèque (fichiers conservés)",
          query=("purge:bool",), confirm="Retirer la bibliothèque du support {key} ?"),
    route("storage", "advisor", "GET", "/api/storage/advisor/format", "système de fichiers conseillé",
          query=("host", "others", "media", "legacy:bool")),
    route("storage", "portable-mount", "POST", "/api/storage/portable/{device_id}/mount", "monter un appareil portable"),
    route("storage", "portable-unmount", "POST", "/api/storage/portable/{device_id}/unmount", "démonter un appareil portable"),
    route("storage", "format-plan", "POST", "/api/storage/format/plan", "préparer le formatage d'un support (jeton)",
          body=("key", "travels:strs"), pos=("key",)),
    route("storage", "format", "POST", "/api/storage/format/execute", "formater un support (efface tout)",
          body=("key", "token", "fs", "label", "confirm", "acknowledged:bool"), pos=("key", "fs", "label"),
          confirm="Formater le support {key} ? Toutes ses données seront effacées."),
    route("storage", "format-active", "GET", "/api/storage/format/active", "formatage en cours"),
    route("storage", "format-job", "GET", "/api/storage/format/jobs/{job_id}", "état d'un formatage"),
    route("storage", "format-cancel", "DELETE", "/api/storage/format/jobs/{job_id}", "annuler un formatage"),
)
