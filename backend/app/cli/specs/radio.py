from __future__ import annotations

from .model import Arg, Call, Spec
from .render import lines
from .route import PAGE, route


SPECS: tuple[Spec, ...] = (
    route("radio-library", "list", "GET", "/api/radio/tracks", "lister les morceaux de la bibliothèque radio",
          query=("q", "artist", "album", "genre", "tag") + PAGE, human=lines("{id}  {title}  ({artist})")),
    route("radio-library", "set", "PUT", "/api/radio/tracks/{track_id}", "modifier les informations et les étiquettes d'un morceau",
          body=("title", "artist", "album", "album_artist", "genre", "year:int", "track_number:int", "disc_number:int", "tags:strs"),
          require_one=True),
    Spec("radio-library", "rm", "supprimer un morceau", lambda c, a: Call("DELETE", f"/api/radio/tracks/{a.track_id}"),
         ("DELETE /api/radio/tracks/{track_id}",), (Arg(("track_id",), "identifiant du morceau", int),),
         lambda p, a: f"Morceau {a.track_id} supprimé.", confirm="Supprimer le morceau {track_id} et son fichier ?"),
    route("radio-library", "get", "GET", "/api/radio/tracks/{track_id}", "détail d'un morceau"),
    route("radio-library", "cover", "POST", "/api/radio/tracks/{track_id}/cover", "remplacer la pochette", files=("file",)),
    route("radio-library", "artists", "GET", "/api/radio/artists", "lister les artistes"),
    route("radio-library", "albums", "GET", "/api/radio/albums", "lister les albums"),
)
