from __future__ import annotations

from app.api.contract import ANNOUNCEMENT_RULE_TYPES, ANNOUNCEMENT_TARGETS

from .model import Spec
from .route import route

_TARGET = "target=" + "|".join(ANNOUNCEMENT_TARGETS)
_RULE = ("rule_type=" + "|".join(ANNOUNCEMENT_RULE_TYPES), "n_tracks:int", "interval_minutes:int", "times_of_day:strs",
         "enabled:bool", _TARGET)

SPECS: tuple[Spec, ...] = (
    route("radio-announcements", "list", "GET", "/api/radio/announcements", "lister les annonces"),
    route("radio-announcements", "add", "POST", "/api/radio/announcements/upload", "importer une annonce",
          files=("file",), body=("description",), pos=("description",)),
    route("radio-announcements", "add-batch", "POST", "/api/radio/announcements/upload-batch", "importer plusieurs annonces",
          files=("files+",)),
    route("radio-announcements", "set", "PUT", "/api/radio/announcements/{announcement_id}", "modifier une annonce",
          body=("description", "enabled:bool"), require_one=True),
    route("radio-announcements", "rm", "DELETE", "/api/radio/announcements/{announcement_id}", "supprimer une annonce",
          confirm="Supprimer l'annonce {announcement_id} ?"),
    route("radio-announcements", "play", "POST", "/api/radio/announcements/play-now", "diffuser une annonce maintenant",
          body=("announcement_id:int", _TARGET), pos=("announcement_id",)),
    route("radio-rules", "list", "GET", "/api/radio/announcement-rules", "lister les règles de rappel"),
    route("radio-rules", "add", "POST", "/api/radio/announcement-rules", "créer une règle de rappel", body=_RULE, pos=("rule_type",)),
    route("radio-rules", "set", "PUT", "/api/radio/announcement-rules/{rule_id}", "remplacer une règle de rappel",
          body=_RULE, pos=("rule_type",)),
    route("radio-rules", "rm", "DELETE", "/api/radio/announcement-rules/{rule_id}", "supprimer une règle de rappel",
          confirm="Supprimer la règle {rule_id} ?"),
)
