from __future__ import annotations

from app.api.contract import ANNOUNCEMENT_RULE_TYPES, ANNOUNCEMENT_TARGETS

from .model import Arg, Call, Spec, UsageError
from .route import PAGE, Field, route

_TARGET = "target=" + "|".join(ANNOUNCEMENT_TARGETS)
_RULE = ("rule_type=" + "|".join(ANNOUNCEMENT_RULE_TYPES), "n_tracks:int", "interval_minutes:int", "times_of_day:strs",
         "enabled:bool", _TARGET)

_RULE_FIELDS = tuple(Field.parse(text, set()) for text in _RULE)


def _rule_set(client, args) -> Call:
    current = next((r for r in client.request("GET", "/api/radio/announcement-rules") or [] if r.get("id") == args.rule_id), None)
    if current is None:
        raise UsageError(f"règle {args.rule_id} introuvable (bobine radio-rules list)")
    body = {key: current.get(key) for key in ("rule_type", "n_tracks", "interval_minutes", "times_of_day", "enabled", "target")}
    body.update({f.name: f.value(args) for f in _RULE_FIELDS if f.provided(args)})
    return Call("PUT", f"/api/radio/announcement-rules/{args.rule_id}", body)


SPECS: tuple[Spec, ...] = (
    route("radio-announcements", "list", "GET", "/api/radio/announcements", "lister les annonces", query=PAGE),
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
    route("radio-rules", "list", "GET", "/api/radio/announcement-rules", "lister les règles de rappel", query=PAGE),
    route("radio-rules", "add", "POST", "/api/radio/announcement-rules", "créer une règle de rappel", body=_RULE, pos=("rule_type",)),
    Spec("radio-rules", "set", "modifier une règle de rappel (le reste est conservé)", _rule_set,
         ("PUT /api/radio/announcement-rules/{rule_id}",),
         (Arg(("rule_id",), "identifiant de la règle", int), *(f.arg() for f in _RULE_FIELDS)),
         lambda p, a: f"Règle {a.rule_id} mise à jour.", needs_one_of=tuple(f.dest for f in _RULE_FIELDS)),
    route("radio-rules", "rm", "DELETE", "/api/radio/announcement-rules/{rule_id}", "supprimer une règle de rappel",
          confirm="Supprimer la règle {rule_id} ?"),
)
