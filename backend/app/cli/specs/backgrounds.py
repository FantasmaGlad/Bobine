from __future__ import annotations

from .model import Arg, Call, Spec
from .render import lines
from .route import PAGE, route


SPECS: tuple[Spec, ...] = (
    route("backgrounds", "list", "GET", "/api/backgrounds", "lister les fonds animés", query=PAGE, human=lines("{id}  {title}")),
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
)
