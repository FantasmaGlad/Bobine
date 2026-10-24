"""Garde-fou du profil Android, qui tourne en Pydantic v1 (Chaquopy n'a pas de pydantic-core) alors
que toutes les autres plateformes sont en v2 (cf. app/utils/_pydantic_compat.py).

Une construction valable seulement en v2 ne casse pas la suite de tests (exécutée en v2) mais
empêche le serveur Android de DÉMARRER : l'application tourne alors sans fin sur son écran de
chargement. Ce test détecte statiquement les deux pièges déjà rencontrés :

  - `Field(max_length=...)` / `min_length` sur une liste (v1 : « constraints are set but not
    enforced » dès l'import du module) -> utiliser `list_max_items` ;
  - appel direct de `.model_dump()` / `.model_validate()` (v2 uniquement) -> passer par
    `getattr(obj, "model_dump", None) or obj.dict`, comme settings.py.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
SEQUENCE_TYPES = {"list", "set", "tuple", "frozenset", "sequence"}
V2_ONLY_CALLS = {"model_dump", "model_dump_json", "model_validate", "model_validate_json"}
CONSTRAINTS_V2_NAMES = {"max_length", "min_length"}


def _sources():
    for path in sorted(APP.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_aucune_contrainte_de_taille_v2_sur_une_liste():
    offenders = []
    for path, tree in _sources():
        for node in ast.walk(tree):
            if not (isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Call)):
                continue
            func = node.value.func
            if getattr(func, "id", getattr(func, "attr", "")) != "Field":
                continue
            annotation = ast.unparse(node.annotation).split("[")[0].lower()
            keywords = {k.arg for k in node.value.keywords}
            if annotation in SEQUENCE_TYPES and keywords & CONSTRAINTS_V2_NAMES:
                offenders.append(f"{path.relative_to(APP.parent)}:{node.lineno} {ast.unparse(node.annotation)}")
    assert not offenders, "Field(max_length/min_length) sur une liste (planterait Android) : utiliser list_max_items — " + ", ".join(offenders)


def test_aucun_appel_direct_a_une_api_pydantic_v2():
    offenders = []
    for path, tree in _sources():
        if path.name == "_pydantic_compat.py":
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in V2_ONLY_CALLS:
                offenders.append(f"{path.relative_to(APP.parent)}:{node.lineno} .{node.func.attr}()")
    assert not offenders, "API Pydantic v2 appelée directement (planterait Android) : " + ", ".join(offenders)


def test_list_max_items_applique_le_plafond_dans_la_version_installee():
    from pydantic import BaseModel, ValidationError

    from app.utils._pydantic_compat import list_max_items

    class Probe(BaseModel):
        items: list[int] = list_max_items(2)
        tags: list[str] = list_max_items(1, default_factory=list)

    assert Probe(items=[1, 2]).tags == []
    for bad in ({"items": [1, 2, 3]}, {"items": [], "tags": ["a", "b"]}):
        try:
            Probe(**bad)
        except ValidationError:
            continue
        raise AssertionError(f"{bad} aurait dû être refusé")
