from __future__ import annotations

from app.api.contract import CHANNELS, DEFAULT_CHANNEL, MEDIA_KINDS, PLAYABLE_MEDIA

from .model import Arg, Call, Spec
from .route import route


def _duration(seconds: float | None) -> str:
    return f"{int(seconds // 60)} min" if seconds else "-"


def _catalog_lines(payload, args) -> str:
    rows = [f"{e['kind']:<15} {e['id']:>5}  {e['title']}  ({e.get('subtitle') or '-'}, {_duration(e.get('duration_seconds'))})"
            + ("" if e.get("available") else "  [indisponible]") for e in (payload or {}).get("items", [])]
    return "\n".join(rows) + f"\n{len(rows)} sur {(payload or {}).get('total', 0)}"


def _play(kind: str) -> Spec:
    family, action, param = PLAYABLE_MEDIA[kind]

    def request(client, args) -> Call:
        return Call("POST", f"/api/{family}/{args.channel}/{action}", {param: args.id})

    route_key = "POST /api/playback/{channel}/{action}" if family == "playback" else "POST /api/radio/{output}/{action}"
    return Spec("play", kind, f"lire un média de type {kind}", request, (route_key,),
                (Arg(("id",), "identifiant (bobine media list)", int),
                 Arg(("--channel",), "canal de diffusion", choices=CHANNELS, default=DEFAULT_CHANNEL)),
                lambda p, a: f"{kind} {a.id} lancé sur {a.channel}.")


SPECS: tuple[Spec, ...] = (
    route("media", "list", "GET", "/api/media", "médias de toutes les bibliothèques, avec leur identifiant de lecture",
          query=("kind=" + "|".join(MEDIA_KINDS), "q", "limit:int", "offset:int"), human=_catalog_lines),
    *(_play(kind) for kind in PLAYABLE_MEDIA),
)
