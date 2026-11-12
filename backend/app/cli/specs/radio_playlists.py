from __future__ import annotations

from .model import Spec
from .route import route

SPECS: tuple[Spec, ...] = (
    route("radio-playlists", "list", "GET", "/api/radio/playlists", "lister les playlists radio"),
    route("radio-playlists", "get", "GET", "/api/radio/playlists/{playlist_id}", "détail d'une playlist radio"),
    route("radio-playlists", "add", "POST", "/api/radio/playlists", "créer une playlist radio",
          body=("name", "track_ids:ints"), pos=("name",)),
    route("radio-playlists", "set", "PUT", "/api/radio/playlists/{playlist_id}", "renommer ou recomposer une playlist radio",
          body=("name", "track_ids:ints"), pos=("name",)),
    route("radio-playlists", "rm", "DELETE", "/api/radio/playlists/{playlist_id}", "supprimer une playlist radio",
          confirm="Supprimer la playlist radio {playlist_id} ?"),
    route("radio-playlists", "track-add", "POST", "/api/radio/playlists/{playlist_id}/tracks", "ajouter un morceau à la fin",
          body=("track_id:int",), pos=("track_id",)),
    route("radio-playlists", "default", "PUT", "/api/radio/playlists/{playlist_id}/default", "en faire l'ambiance par défaut"),
    route("radio-playlists", "default-rm", "DELETE", "/api/radio/playlists/{playlist_id}/default", "ne plus en faire l'ambiance par défaut"),
)
