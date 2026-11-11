"""Commandes d'écriture de `bobine`, déclarées en données : une ligne de `SPECS` ajoute la commande, son aide, ses arguments,
la route appelée et sa confirmation. `app.cli` en construit le parser et l'exécution ; `backend/tests/test_cli_contract.py`
vérifie que chaque route déclarée figure dans `app/cli/routes.py`.

Ajouter un bouton à l'interface qui appelle une nouvelle route : ajouter la route à `COVERED` (ou à `EXEMPT`) dans
`routes.py`, et, si une commande a du sens, une `Spec` ici. Aucune dépendance en dehors de la bibliothèque standard.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any, Callable

from app.api_contract import OVERRIDE_ACTIONS, SCHEDULE_CHANNELS, SCHEDULE_TARGETS



class UsageError(ValueError):
    """Arguments incohérents : code de sortie 2."""


@dataclass(frozen=True)
class Arg:
    flags: tuple[str, ...]
    help: str = ""
    kind: Callable[[str], Any] | None = None
    choices: tuple[str, ...] | None = None
    action: str | None = None
    default: Any = None
    nargs: str | None = None
    dest: str | None = None

    def add_to(self, parser: argparse.ArgumentParser) -> None:
        options: dict[str, Any] = {"help": self.help}
        if self.action:
            options["action"] = self.action
        else:
            if self.kind:
                options["type"] = self.kind
            if self.choices:
                options["choices"] = self.choices
            if self.nargs:
                options["nargs"] = self.nargs
        if self.default is not None:
            options["default"] = self.default
        if self.dest and self.flags[0].startswith("-"):
            options["dest"] = self.dest
        parser.add_argument(*self.flags, **options)


@dataclass(frozen=True)
class Call:
    method: str
    path: str
    body: Any = None
    query: dict | None = None


@dataclass(frozen=True)
class Spec:
    command: str  # commande de premier niveau (existante ou nouvelle)
    action: str  # sous-commande
    help: str
    request: Callable[[Any, argparse.Namespace], Call]  # (client, args) -> appel ; le client sert à lire l'état avant d'écrire
    covers: tuple[str, ...]  # « METHODE /chemin OpenAPI » (contrôlé par test_cli_contract)
    arguments: tuple[Arg, ...] = ()
    human: Callable[[Any, argparse.Namespace], str] = lambda payload, args: "Fait."
    confirm: str | None = None  # texte de la demande : l'écriture exige alors --yes
    needs_one_of: tuple[str, ...] = field(default=())  # au moins une de ces options (attributs de `args`)


def _video_ids(values: list[int] | None) -> list[dict]:
    return [{"video_id": video_id, "position": index} for index, video_id in enumerate(values or [])]


def _playlist_set(client, args) -> Call:
    current = client.request("GET", f"/api/playlists/{args.playlist_id}")
    name = args.name if args.name is not None else current.get("name")
    if args.clear:
        items: list[dict] = []
    elif args.video is not None:
        items = _video_ids(args.video)
    else:
        items = [{"video_id": item["video"]["id"], "position": i} for i, item in enumerate(current.get("items") or []) if item.get("video")]
    return Call("PUT", f"/api/playlists/{args.playlist_id}", {"name": name, "items": items})


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
    body = {"channel": "cable", "active": True}
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


def _fields(args, names: tuple[str, ...]) -> dict:
    return {name: getattr(args, name) for name in names if getattr(args, name, None) is not None}


SCHEDULE_OPTIONS = (
    Arg(("--at",), "date et heure ISO 8601 d'une programmation ponctuelle (2026-12-24T09:00:00+01:00)"),
    Arg(("--days",), "jours d'une récurrence, de 0 (lundi) à 6 (dimanche), séparés par des virgules"),
    Arg(("--time",), "heure d'une récurrence, HH:MM"),
    Arg(("--end",), "fin de la fenêtre radio, HH:MM"),
    Arg(("--all-day",), "radio : toute la journée (24 h sur 24)", action="store_true"),
    Arg(("--active",), "activer la programmation", action="store_true"),
    Arg(("--inactive",), "la désactiver", action="store_true"),
)

def _lines(template: str):
    """Formateur de liste : une ligne par élément, `template` reçoit le dictionnaire de l'élément."""
    return lambda payload, args: "\n".join(template.format_map(_Blank(item)) for item in (payload or []) if isinstance(item, dict))


class _Blank(dict):
    def __missing__(self, key: str) -> str:
        return "-"


SPECS: tuple[Spec, ...] = (
    Spec("library", "set", "modifier titre, programme, release ou description d'une vidéo",
         lambda c, a: Call("PUT", f"/api/videos/{a.video_id}", _fields(a, ("title", "program", "release", "description"))),
         ("PUT /api/videos/{video_id}",),
         (Arg(("video_id",), "identifiant de la vidéo", int), Arg(("--title",)), Arg(("--program",)), Arg(("--release",)), Arg(("--description",))),
         lambda p, a: f"Vidéo {a.video_id} mise à jour : {p.get('title')}", needs_one_of=("title", "program", "release", "description")),
    Spec("library", "rm", "supprimer une vidéo et son fichier (elle quitte aussi les playlists et le planning)",
         lambda c, a: Call("DELETE", f"/api/videos/{a.video_id}"), ("DELETE /api/videos/{video_id}",),
         (Arg(("video_id",), "identifiant de la vidéo", int),),
         lambda p, a: f"Vidéo {a.video_id} supprimée.", confirm="Supprimer la vidéo {video_id} et son fichier ?"),
    Spec("playlists", "add", "créer une playlist vidéo",
         lambda c, a: Call("POST", "/api/playlists", {"name": a.name, "items": _video_ids(a.video)}), ("POST /api/playlists",),
         (Arg(("name",), "nom de la playlist"), Arg(("--video",), "identifiant d'une vidéo (répétable, dans l'ordre)", int, action="append")),
         lambda p, a: f"Playlist {p.get('id')} créée : {p.get('name')}"),
    Spec("playlists", "set", "renommer ou recomposer une playlist (sans option, rien ne change)", _playlist_set, ("PUT /api/playlists/{playlist_id}",),
         (Arg(("playlist_id",), "identifiant de la playlist", int), Arg(("--name",), "nouveau nom"),
          Arg(("--video",), "remplace le contenu : identifiant d'une vidéo (répétable, dans l'ordre)", int, action="append"),
          Arg(("--clear",), "vide la playlist", action="store_true")),
         lambda p, a: f"Playlist {a.playlist_id} mise à jour : {p.get('name')}", needs_one_of=("name", "video", "clear")),
    Spec("playlists", "rm", "supprimer une playlist", lambda c, a: Call("DELETE", f"/api/playlists/{a.playlist_id}"),
         ("DELETE /api/playlists/{playlist_id}",), (Arg(("playlist_id",), "identifiant de la playlist", int),),
         lambda p, a: f"Playlist {a.playlist_id} supprimée.", confirm="Supprimer la playlist {playlist_id} ?"),
    Spec("playlists", "dup", "dupliquer une playlist", lambda c, a: Call("POST", f"/api/playlists/{a.playlist_id}/duplicate"),
         ("POST /api/playlists/{playlist_id}/duplicate",), (Arg(("playlist_id",), "identifiant de la playlist", int),),
         lambda p, a: f"Copie créée : {p.get('id')}  {p.get('name')}"),
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
    Spec("update", "acknowledge", "acquitter le résultat de la dernière mise à jour", lambda c, a: Call("POST", "/api/updates/acknowledge"),
         ("POST /api/updates/acknowledge",), (), lambda p, a: "Mise à jour acquittée."),
    Spec("audio", "list", "lister les cours audio", lambda c, a: Call("GET", "/api/audio"), ("GET /api/audio",), (),
         _lines("{id}  {title}  ({program} {release})")),
    Spec("audio", "get", "détail d'un cours audio et de ses pistes", lambda c, a: Call("GET", f"/api/audio/{a.course_id}"),
         ("GET /api/audio/{course_id}",), (Arg(("course_id",), "identifiant du cours", int),),
         lambda p, a: f"{p.get('id')}  {p.get('title')}\n" + "\n".join(f"  {t.get('number')}  {t.get('title')}" for t in p.get("tracks") or [])),
    Spec("audio", "set", "modifier titre, programme ou release d'un cours audio",
         lambda c, a: Call("PUT", f"/api/audio/{a.course_id}", _fields(a, ("title", "program", "release"))), ("PUT /api/audio/{course_id}",),
         (Arg(("course_id",), "identifiant du cours", int), Arg(("--title",)), Arg(("--program",)), Arg(("--release",))),
         lambda p, a: f"Cours {a.course_id} mis à jour : {p.get('title')}", needs_one_of=("title", "program", "release")),
    Spec("audio", "rm", "supprimer un cours audio et ses fichiers", lambda c, a: Call("DELETE", f"/api/audio/{a.course_id}"),
         ("DELETE /api/audio/{course_id}",), (Arg(("course_id",), "identifiant du cours", int),),
         lambda p, a: f"Cours {a.course_id} supprimé.", confirm="Supprimer le cours audio {course_id} et ses fichiers ?"),
    Spec("backgrounds", "list", "lister les fonds animés", lambda c, a: Call("GET", "/api/backgrounds"), ("GET /api/backgrounds",), (),
         _lines("{id}  {title}")),
    Spec("backgrounds", "get", "détail d'un fond animé", lambda c, a: Call("GET", f"/api/backgrounds/{a.background_id}"),
         ("GET /api/backgrounds/{background_id}",), (Arg(("background_id",), "identifiant du fond", int),),
         lambda p, a: f"{p.get('id')}  {p.get('title')}"),
    Spec("backgrounds", "set", "renommer un fond animé",
         lambda c, a: Call("PUT", f"/api/backgrounds/{a.background_id}", {"title": a.title}), ("PUT /api/backgrounds/{background_id}",),
         (Arg(("background_id",), "identifiant du fond", int), Arg(("--title",), "nouveau titre")),
         lambda p, a: f"Fond {a.background_id} renommé : {p.get('title')}", needs_one_of=("title",)),
    Spec("backgrounds", "rm", "supprimer un fond animé", lambda c, a: Call("DELETE", f"/api/backgrounds/{a.background_id}"),
         ("DELETE /api/backgrounds/{background_id}",), (Arg(("background_id",), "identifiant du fond", int),),
         lambda p, a: f"Fond {a.background_id} supprimé.", confirm="Supprimer le fond animé {background_id} ?"),
    Spec("radio-library", "list", "lister les morceaux de la bibliothèque radio", lambda c, a: Call("GET", "/api/radio/tracks"),
         ("GET /api/radio/tracks",), (), _lines("{id}  {title}  ({artist})")),
    Spec("radio-library", "set", "modifier les informations d'un morceau",
         lambda c, a: Call("PUT", f"/api/radio/tracks/{a.track_id}", _fields(a, ("title", "artist", "album", "genre", "year"))),
         ("PUT /api/radio/tracks/{track_id}",),
         (Arg(("track_id",), "identifiant du morceau", int), Arg(("--title",)), Arg(("--artist",)), Arg(("--album",)), Arg(("--genre",)),
          Arg(("--year",), kind=int)),
         lambda p, a: f"Morceau {a.track_id} mis à jour : {p.get('title')}", needs_one_of=("title", "artist", "album", "genre", "year")),
    Spec("radio-library", "rm", "supprimer un morceau", lambda c, a: Call("DELETE", f"/api/radio/tracks/{a.track_id}"),
         ("DELETE /api/radio/tracks/{track_id}",), (Arg(("track_id",), "identifiant du morceau", int),),
         lambda p, a: f"Morceau {a.track_id} supprimé.", confirm="Supprimer le morceau {track_id} et son fichier ?"),
)
