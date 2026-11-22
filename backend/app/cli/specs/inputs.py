from __future__ import annotations

from typing import Any

from .model import Arg, Call, Spec
from .route import route


def _table(payload: Any, _args: Any) -> str:
    overrides = payload.get("overrides", {})
    rows = [f"{source}  {' > '.join(actions)}{'  (personnalisé)' if source in overrides else ''}"
            for source, actions in sorted(payload.get("bindings", {}).items())]
    disabled = [f"{source}  désactivée" for source, actions in sorted(overrides.items()) if not actions]
    return "\n".join(rows + disabled)


SPECS: tuple[Spec, ...] = (
    route("inputs", "list", "GET", "/api/settings/inputs", "entrées (clavier, télécommande, manette) et leurs actions",
          human=_table),
    route("inputs", "set", "PATCH", "/api/settings/inputs",
          "associer une entrée (key:<touche>, code:<n>, pad:<n>) à des actions, par ordre de préférence",
          body=("input", "actions:strs"), pos=("input", "actions"), human=_table),
    Spec("inputs", "off", "désactiver une entrée",
         lambda _client, args: Call("PATCH", "/api/settings/inputs", {"input": args.input, "actions": []}),
         ("PATCH /api/settings/inputs",), (Arg(("input",), "entrée"),), _table),
    route("inputs", "default", "PATCH", "/api/settings/inputs", "rendre à une entrée sa valeur par défaut",
          body=("input",), pos=("input",), human=_table),
    route("inputs", "reset", "DELETE", "/api/settings/inputs", "rendre toutes les entrées à la table par défaut",
          confirm="Rendre toutes les entrées à la table par défaut ?", human=_table),
)
