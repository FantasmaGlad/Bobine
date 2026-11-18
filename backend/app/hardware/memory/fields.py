Found = dict[str, str]
FIELDS = ("brand", "type", "freq")
_BLANK_BRANDS = ("not specified", "not available", "unknown", "n/a", "other", "none")
_BLANK_TYPES = ("unknown", "other", "none", "n/a")


def brand(value: str) -> str:
    return value if value and value.lower() not in _BLANK_BRANDS else ""


def kind(value: str) -> str:
    return value if value and value.lower() not in _BLANK_TYPES else ""


def keep(found: Found, field: str, value: str) -> None:
    if value and field not in found:
        found[field] = value
