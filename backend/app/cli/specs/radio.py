from __future__ import annotations

from .model import Arg, Call, Spec
from .render import lines
from .route import route
from .fields import provided


SPECS: tuple[Spec, ...] = (
    Spec("radio-library", "list", "lister les morceaux de la bibliothèque radio", lambda c, a: Call("GET", "/api/radio/tracks"),
         ("GET /api/radio/tracks",), (), lines("{id}  {title}  ({artist})")),
    Spec("radio-library", "set", "modifier les informations d'un morceau",
         lambda c, a: Call("PUT", f"/api/radio/tracks/{a.track_id}", provided(a, ("title", "artist", "album", "genre", "year"))),
         ("PUT /api/radio/tracks/{track_id}",),
         (Arg(("track_id",), "identifiant du morceau", int), Arg(("--title",)), Arg(("--artist",)), Arg(("--album",)), Arg(("--genre",)),
          Arg(("--year",), kind=int)),
         lambda p, a: f"Morceau {a.track_id} mis à jour : {p.get('title')}", needs_one_of=("title", "artist", "album", "genre", "year")),
    Spec("radio-library", "rm", "supprimer un morceau", lambda c, a: Call("DELETE", f"/api/radio/tracks/{a.track_id}"),
         ("DELETE /api/radio/tracks/{track_id}",), (Arg(("track_id",), "identifiant du morceau", int),),
         lambda p, a: f"Morceau {a.track_id} supprimé.", confirm="Supprimer le morceau {track_id} et son fichier ?"),
    route("radio-library", "get", "GET", "/api/radio/tracks/{track_id}", "détail d'un morceau"),
    route("radio-library", "cover", "POST", "/api/radio/tracks/{track_id}/cover", "remplacer la pochette", files=("file",)),
    route("radio-library", "artists", "GET", "/api/radio/artists", "lister les artistes"),
    route("radio-library", "albums", "GET", "/api/radio/albums", "lister les albums"),
)
