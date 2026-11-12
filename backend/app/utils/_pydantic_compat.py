"""Compatibilité Pydantic v1 (profil Android) / v2 (toutes les autres plateformes) — cf."""

try:
    from pydantic import computed_field

    class _ComputedFieldsCompatMixin:
        pass

except ImportError:

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
    """`Field(...)` plafonnant la taille d'une LISTE, valable en Pydantic v1 comme en v2."""
    from pydantic import VERSION, Field

    if VERSION.startswith("1."):
        return Field(max_items=limit, **kwargs)
    return Field(max_length=limit, **kwargs)
