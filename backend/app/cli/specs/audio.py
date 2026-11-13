from __future__ import annotations

from .model import Arg, Call, Spec
from .render import lines
from .route import PAGE, route
from .fields import provided


SPECS: tuple[Spec, ...] = (
    route("audio", "list", "GET", "/api/audio", "lister les cours audio", query=PAGE, human=lines("{id}  {title}  ({program} {release})")),
    Spec("audio", "get", "détail d'un cours audio et de ses pistes", lambda c, a: Call("GET", f"/api/audio/{a.course_id}"),
         ("GET /api/audio/{course_id}",), (Arg(("course_id",), "identifiant du cours", int),),
         lambda p, a: f"{p.get('id')}  {p.get('title')}\n" + "\n".join(f"  {t.get('number')}  {t.get('title')}" for t in p.get("tracks") or [])),
    Spec("audio", "set", "modifier titre, programme ou release d'un cours audio",
         lambda c, a: Call("PUT", f"/api/audio/{a.course_id}", provided(a, ("title", "program", "release"))), ("PUT /api/audio/{course_id}",),
         (Arg(("course_id",), "identifiant du cours", int), Arg(("--title",)), Arg(("--program",)), Arg(("--release",))),
         lambda p, a: f"Cours {a.course_id} mis à jour : {p.get('title')}", needs_one_of=("title", "program", "release")),
    Spec("audio", "rm", "supprimer un cours audio et ses fichiers", lambda c, a: Call("DELETE", f"/api/audio/{a.course_id}"),
         ("DELETE /api/audio/{course_id}",), (Arg(("course_id",), "identifiant du cours", int),),
         lambda p, a: f"Cours {a.course_id} supprimé.", confirm="Supprimer le cours audio {course_id} et ses fichiers ?"),
    route("audio", "tracks", "GET", "/api/audio/tracks", "lister toutes les pistes", query=PAGE),
    route("audio", "programs", "GET", "/api/audio/programs", "programmes connus"),
    route("audio", "track-set", "PUT", "/api/audio/{course_id}/tracks/{track_id}", "modifier une piste",
          body=("title", "number:int", "background_id:int", "clear_background:bool"), require_one=True),
    route("audio", "reorder", "PUT", "/api/audio/{course_id}/tracks/reorder", "réordonner les pistes",
          body=("track_ids:ints",), pos=("track_ids",)),
)
