from __future__ import annotations

from .model import Call, Spec
from .route import route


SPECS: tuple[Spec, ...] = (
    Spec("update", "acknowledge", "acquitter le résultat de la dernière mise à jour", lambda c, a: Call("POST", "/api/updates/acknowledge"),
         ("POST /api/updates/acknowledge",), (), lambda p, a: "Mise à jour acquittée."),
    route("update", "tor-check", "POST", "/api/updates/tor-check", "tester le passage par Tor (contacte check.torproject.org)",
          body=("proxy",)),
)
