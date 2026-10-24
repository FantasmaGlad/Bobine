"""Compatibilité Pydantic v1 (profil Android) / v2 (toutes les autres
plateformes) — cf. docs/ARCHITECTURE.md §3.1 : `pydantic-core` (donc
Pydantic v2, donc FastAPI) n'a aucune distribution Android réelle, d'où un
downgrade Pydantic v1 sur ce seul profil.

`computed_field` n'a pas d'équivalent natif en v1 : une propriété Python
normale n'est PAS incluse dans `.dict()` par défaut. `_ComputedFieldsCompatMixin`
comble cet écart uniquement quand c'est nécessaire (v1) ; sur v2 c'est une
classe vide, sans effet, puisque Pydantic v2 gère déjà `computed_field`
nativement.
"""

try:
    from pydantic import computed_field

    class _ComputedFieldsCompatMixin:
        pass

except ImportError:  # Pydantic v1 (profil Android)

    def computed_field(prop):
        prop.fget.__is_computed_field__ = True
        return prop

    class _ComputedFieldsCompatMixin:
        def dict(self, *args, **kwargs):
            data = super().dict(*args, **kwargs)
            for name in dir(type(self)):
                attr = getattr(type(self), name, None)
                if isinstance(attr, property) and getattr(attr.fget, "__is_computed_field__", False):
                    data[name] = getattr(self, name)
            return data


def list_max_items(limit: int, **kwargs):
    """`Field(...)` plafonnant la taille d'une LISTE, valable en Pydantic v1 comme en v2.

    Le plafond de taille d'une liste s'écrit `max_length` en v2 et `max_items` en v1 ; v1 refuse
    `max_length` sur une liste (« constraints are set but not enforced ») au moment de l'import
    du module, ce qui empêchait tout le serveur Android de démarrer. Les `str` n'ont pas ce
    problème : `max_length` y est valable dans les deux versions."""
    from pydantic import VERSION, Field

    if VERSION.startswith("1."):
        return Field(max_items=limit, **kwargs)
    return Field(max_length=limit, **kwargs)
