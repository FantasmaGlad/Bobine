from __future__ import annotations

from .model import Arg, Call, Spec
from .render import lines
from .route import PAGE, route


SPECS: tuple[Spec, ...] = (
    route("visuals", "list", "GET", "/api/visuals", "lister les visuels diffusés", query=PAGE, human=lines("{id}  {title}")),
    Spec("visuals", "get", "détail d'un visuel", lambda c, a: Call("GET", f"/api/visuals/{a.visual_id}"),
         ("GET /api/visuals/{visual_id}",), (Arg(("visual_id",), "identifiant du visuel", int),),
         lambda p, a: f"{p.get('id')}  {p.get('title')}"),
    Spec("visuals", "set", "renommer un visuel",
         lambda c, a: Call("PUT", f"/api/visuals/{a.visual_id}", {"title": a.title}), ("PUT /api/visuals/{visual_id}",),
         (Arg(("visual_id",), "identifiant du visuel", int), Arg(("--title",), "nouveau titre")),
         lambda p, a: f"Visuel {a.visual_id} renommé : {p.get('title')}", needs_one_of=("title",)),
    Spec("visuals", "rm", "supprimer un visuel", lambda c, a: Call("DELETE", f"/api/visuals/{a.visual_id}"),
         ("DELETE /api/visuals/{visual_id}",), (Arg(("visual_id",), "identifiant du visuel", int),),
         lambda p, a: f"Visuel {a.visual_id} supprimé.", confirm="Supprimer le visuel {visual_id} ?"),
)
