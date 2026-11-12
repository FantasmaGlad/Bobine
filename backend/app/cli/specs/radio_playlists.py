from __future__ import annotations

from .model import Arg, Call, Spec
from .route import _ints, route


def _set(client, args) -> Call:
    current = client.request("GET", f"/api/radio/playlists/{args.playlist_id}")
    track_ids = _ints(args.track_ids) if args.track_ids is not None else [i["track"]["id"] for i in current.get("items") or []]
    return Call("PUT", f"/api/radio/playlists/{args.playlist_id}", {"name": args.name or current.get("name"), "track_ids": track_ids})

SPECS: tuple[Spec, ...] = (
    route("radio-playlists", "list", "GET", "/api/radio/playlists", "lister les playlists radio"),
    route("radio-playlists", "get", "GET", "/api/radio/playlists/{playlist_id}", "détail d'une playlist radio"),
    route("radio-playlists", "add", "POST", "/api/radio/playlists", "créer une playlist radio",
          body=("name", "track_ids:ints"), pos=("name",)),
    Spec("radio-playlists", "set", "renommer ou recomposer une playlist radio (le reste est conservé)", _set,
         ("PUT /api/radio/playlists/{playlist_id}",),
         (Arg(("playlist_id",), "identifiant de la playlist radio", int), Arg(("--name",), "nouveau nom"),
          Arg(("--track-ids",), "morceaux, dans l'ordre (1,2,3)", dest="track_ids")),
         lambda p, a: f"Playlist radio {a.playlist_id} mise à jour.", needs_one_of=("name", "track_ids")),
    route("radio-playlists", "rm", "DELETE", "/api/radio/playlists/{playlist_id}", "supprimer une playlist radio",
          confirm="Supprimer la playlist radio {playlist_id} ?"),
    route("radio-playlists", "track-add", "POST", "/api/radio/playlists/{playlist_id}/tracks", "ajouter un morceau à la fin",
          body=("track_id:int",), pos=("track_id",)),
    route("radio-playlists", "default", "PUT", "/api/radio/playlists/{playlist_id}/default", "en faire l'ambiance par défaut"),
    route("radio-playlists", "default-rm", "DELETE", "/api/radio/playlists/{playlist_id}/default", "ne plus en faire l'ambiance par défaut"),
)
