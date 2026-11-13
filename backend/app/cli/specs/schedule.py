from __future__ import annotations

from typing import Any

from app.api.contract import DEFAULT_CHANNEL, OVERRIDE_ACTIONS, SCHEDULE_CHANNELS, SCHEDULE_TARGETS

from .model import Arg, Call, Spec, UsageError
from .route import PAGE, route


def _schedule_body(args, base: dict | None = None) -> dict:
    body = dict(base or {})
    if getattr(args, "target_type", None):
        body["target_type"], body["target_id"] = args.target_type, args.target_id
    if getattr(args, "channel", None):
        body["channel"] = args.channel
    if args.at and (args.days or args.time):
        raise UsageError("--at (ponctuelle) et --days/--time (récurrente) s'excluent")
    if args.at:
        body.update(schedule_type="once", run_at=args.at, days_of_week=None, time_of_day=None)
    elif args.days or args.time:
        days = [int(d) for d in args.days.split(",")] if args.days else body.get("days_of_week")
        if not days or not (args.time or body.get("time_of_day")):
            raise UsageError("une programmation récurrente demande --days (0 lundi à 6 dimanche) et --time HH:MM")
        body.update(schedule_type="recurring", days_of_week=days, time_of_day=args.time or body.get("time_of_day"), run_at=None)
    if args.end is not None:
        body["end_time"] = args.end
    if args.all_day:
        body["is_24_7"] = True
    if args.active:
        body["active"] = True
    if args.inactive:
        body["active"] = False
    return body


def _schedule_add(client, args) -> Call:
    body = {"channel": DEFAULT_CHANNEL, "active": True}
    body = _schedule_body(args, body)
    if "schedule_type" not in body:
        raise UsageError("indiquer --at (ponctuelle) ou --days et --time (récurrente)")
    return Call("POST", "/api/schedule", body)


def _schedule_set(client, args) -> Call:
    current = client.request("GET", f"/api/schedule/{args.schedule_id}")
    base = {key: current.get(key) for key in ("target_type", "target_id", "channel", "schedule_type", "run_at", "days_of_week",
                                              "time_of_day", "active", "end_time", "is_24_7")}
    return Call("PUT", f"/api/schedule/{args.schedule_id}", _schedule_body(args, base))


def _override(client, args) -> Call:
    body: dict[str, Any] = {"occurrence_date": args.date, "action": args.action}
    if args.action == "replaced":
        if not args.replace_type or args.replace_id is None:
            raise UsageError("--action replaced demande --replace-type et --replace-id")
        body.update(replacement_target_type=args.replace_type, replacement_target_id=args.replace_id)
    return Call("POST", f"/api/schedule/{args.schedule_id}/overrides", body)



SCHEDULE_OPTIONS = (
    Arg(("--at",), "date et heure ISO 8601 d'une programmation ponctuelle (2026-12-24T09:00:00+01:00)"),
    Arg(("--days",), "jours d'une récurrence, de 0 (lundi) à 6 (dimanche), séparés par des virgules"),
    Arg(("--time",), "heure d'une récurrence, HH:MM"),
    Arg(("--end",), "fin de la fenêtre radio, HH:MM"),
    Arg(("--all-day",), "radio : toute la journée (24 h sur 24)", action="store_true"),
    Arg(("--active",), "activer la programmation", action="store_true"),
    Arg(("--inactive",), "la désactiver", action="store_true"),
)



SPECS: tuple[Spec, ...] = (
    Spec("schedule", "add", "créer une programmation (ponctuelle ou récurrente)", _schedule_add, ("POST /api/schedule",),
         (Arg(("target_type",), "ce qui est diffusé", choices=SCHEDULE_TARGETS), Arg(("target_id",), "identifiant de la vidéo ou de la playlist", int),
          Arg(("--channel",), "canal (câblé par défaut)", choices=SCHEDULE_CHANNELS), *SCHEDULE_OPTIONS),
         lambda p, a: f"Programmation {p.get('id')} créée ({p.get('channel')})."),
    Spec("schedule", "set", "modifier une programmation (les champs non cités restent)", _schedule_set, ("PUT /api/schedule/{schedule_id}",),
         (Arg(("schedule_id",), "identifiant de la programmation", int), *SCHEDULE_OPTIONS),
         lambda p, a: f"Programmation {a.schedule_id} mise à jour.", needs_one_of=("at", "days", "time", "end", "all_day", "active", "inactive")),
    Spec("schedule", "rm", "supprimer une programmation", lambda c, a: Call("DELETE", f"/api/schedule/{a.schedule_id}"),
         ("DELETE /api/schedule/{schedule_id}",), (Arg(("schedule_id",), "identifiant de la programmation", int),),
         lambda p, a: f"Programmation {a.schedule_id} supprimée.", confirm="Supprimer la programmation {schedule_id} ?"),
    Spec("schedule", "override", "annuler ou remplacer une occurrence d'une programmation récurrente", _override,
         ("POST /api/schedule/{schedule_id}/overrides",),
         (Arg(("schedule_id",), "identifiant de la programmation", int), Arg(("--date",), "jour de l'occurrence, YYYY-MM-DD"),
          Arg(("--action",), "annuler ou remplacer", choices=OVERRIDE_ACTIONS, default="cancelled"),
          Arg(("--replace-type",), "avec replaced : ce qui remplace", choices=SCHEDULE_TARGETS, dest="replace_type"),
          Arg(("--replace-id",), "avec replaced : identifiant du remplaçant", int, dest="replace_id")),
         lambda p, a: f"Exception {p.get('id')} créée pour le {a.date}.", needs_one_of=("date",)),
    Spec("schedule", "override-rm", "rétablir une occurrence (retirer son exception)",
         lambda c, a: Call("DELETE", f"/api/schedule/{a.schedule_id}/overrides/{a.override_id}"),
         ("DELETE /api/schedule/{schedule_id}/overrides/{override_id}",),
         (Arg(("schedule_id",), "identifiant de la programmation", int), Arg(("override_id",), "identifiant de l'exception", int)),
         lambda p, a: "Occurrence rétablie."),
    route("schedule", "occurrences", "GET", "/api/schedule/occurrences", "occurrences entre deux dates (ISO 8601)",
          query=("start", "end", "channel=" + "|".join(SCHEDULE_CHANNELS)) + PAGE, pos=("start", "end")),
)
