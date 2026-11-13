from __future__ import annotations

from .model import Arg, Call, Spec
from .route import route


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




def _audio_items(track_ids: list[int] | None, backgrounds: dict[int, int | None] | None = None) -> list[dict]:
    return [{"audio_track_id": track_id, "position": index, "background_id": (backgrounds or {}).get(track_id)}
            for index, track_id in enumerate(track_ids or [])]


def _audio_playlist_add(client, args) -> Call:
    return Call("POST", "/api/audio-playlists", {"name": args.name, "items": _audio_items(args.track)})


def _audio_playlist_set(client, args) -> Call:
    current = client.request("GET", f"/api/audio-playlists/{args.playlist_id}")
    name = args.name if args.name is not None else current.get("name")
    if args.clear:
        items: list[dict] = []
    else:
        kept = [item for item in current.get("items") or [] if item.get("track")]
        backgrounds = {item["track"]["id"]: (item.get("background") or {}).get("id") for item in kept}
        items = _audio_items(args.track if args.track is not None else [item["track"]["id"] for item in kept], backgrounds)
    return Call("PUT", f"/api/audio-playlists/{args.playlist_id}", {"name": name, "items": items})


_AUDIO_PLAYLIST_ID = Arg(("playlist_id",), "identifiant de la playlist audio", int)
_TRACK = Arg(("--track",), "identifiant d'une piste audio (répétable, dans l'ordre)", int, action="append")


SPECS: tuple[Spec, ...] = (
    Spec("playlists", "add", "créer une playlist vidéo",
         lambda c, a: Call("POST", "/api/playlists", {"name": a.name, "items": _video_ids(a.video)}), ("POST /api/playlists",),
         (Arg(("name",), "nom de la playlist"), Arg(("--video",), "identifiant d'une vidéo (répétable, dans l'ordre)", int, action="append")),
         lambda p, a: f"Playlist {p.get('id')} créée : {p.get('name')}"),
    Spec("playlists", "set", "renommer ou recomposer une playlist", _playlist_set, ("PUT /api/playlists/{playlist_id}",),
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
    route("audio-playlists", "list", "GET", "/api/audio-playlists", "lister les playlists audio"),
    route("audio-playlists", "get", "GET", "/api/audio-playlists/{playlist_id}", "détail d'une playlist audio"),
    Spec("audio-playlists", "add", "créer une playlist audio", _audio_playlist_add, ("POST /api/audio-playlists",),
         (Arg(("name",), "nom de la playlist"), _TRACK), lambda p, a: f"Playlist audio {p.get('id')} créée : {p.get('name')}"),
    Spec("audio-playlists", "set", "renommer ou recomposer une playlist audio", _audio_playlist_set,
         ("PUT /api/audio-playlists/{playlist_id}",),
         (_AUDIO_PLAYLIST_ID, Arg(("--name",), "nouveau nom"), _TRACK, Arg(("--clear",), "vide la playlist", action="store_true")),
         lambda p, a: f"Playlist audio {a.playlist_id} mise à jour.", needs_one_of=("name", "track", "clear")),
    route("audio-playlists", "rm", "DELETE", "/api/audio-playlists/{playlist_id}", "supprimer une playlist audio",
          confirm="Supprimer la playlist audio {playlist_id} ?"),
    route("audio-playlists", "dup", "POST", "/api/audio-playlists/{playlist_id}/duplicate", "dupliquer une playlist audio"),
)
