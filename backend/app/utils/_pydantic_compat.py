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
