from __future__ import annotations

def provided(args, names: tuple[str, ...]) -> dict:
    return {name: getattr(args, name) for name in names if getattr(args, name, None) is not None}
