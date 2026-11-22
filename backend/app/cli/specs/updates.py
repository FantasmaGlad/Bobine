from __future__ import annotations

from .model import Call, Spec


SPECS: tuple[Spec, ...] = (
    Spec("update", "acknowledge", "acquitter le résultat de la dernière mise à jour", lambda c, a: Call("POST", "/api/updates/acknowledge"),
         ("POST /api/updates/acknowledge",), (), lambda p, a: "Mise à jour acquittée."),
)
