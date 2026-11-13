from __future__ import annotations

import re
from typing import Any

from app.api.errors import CODE_BY_STATUS

_ENUM = re.compile(r"^\^\(([^()]*)\)\$$")


def _resolve(schema: dict, components: dict) -> dict:
    while "$ref" in schema:
        schema = components[schema["$ref"].rsplit("/", 1)[-1]]
    return schema


def _type(schema: dict, components: dict) -> str:
    schema = _resolve(schema, components)
    options = schema.get("anyOf") or schema.get("oneOf")
    if options:
        return " | ".join(dict.fromkeys(_type(o, components) for o in options if o.get("type") != "null")) or "null"
    if schema.get("type") == "array":
        return f"{_type(schema.get('items', {}), components)}[]"
    return schema.get("type") or ("enum" if "enum" in schema else "object")


def _choices(schema: dict, components: dict) -> list[str] | None:
    schema = _resolve(schema, components)
    for option in schema.get("anyOf", [schema]):
        option = _resolve(option, components)
        if "enum" in option:
            return [str(v) for v in option["enum"]]
        match = _ENUM.match(option.get("pattern", ""))
        if match:
            return match.group(1).split("|")
    return None


def _field(name: str, schema: dict, required: bool, components: dict) -> dict[str, Any]:
    return {"name": name, "type": _type(schema, components), "required": required, "choices": _choices(schema, components)}


def _parameters(operation: dict, where: str, components: dict) -> list[dict[str, Any]]:
    return [_field(p["name"], p.get("schema", {}), bool(p.get("required")), components)
            for p in operation.get("parameters", []) if p["in"] == where]


def _body(operation: dict, components: dict) -> dict[str, Any] | None:
    content = operation.get("requestBody", {}).get("content", {})
    for media, spec in content.items():
        schema = _resolve(spec.get("schema", {}), components)
        required = set(schema.get("required", []))
        fields = [_field(n, s, n in required, components) for n, s in schema.get("properties", {}).items()]
        return {"format": "multipart" if "form-data" in media else "json", "fields": fields}
    return None


def _summary(operation: dict) -> str:
    return (operation.get("description") or operation.get("summary") or "").strip().split("\n")[0]


def api_reference(openapi: dict[str, Any]) -> dict[str, Any]:
    components = openapi.get("components", {}).get("schemas", {})
    groups: dict[str, list[dict[str, Any]]] = {}
    for path, operations in openapi["paths"].items():
        group = path.split("/")[2] if path.startswith("/api/") else path.strip("/")
        for method, operation in operations.items():
            groups.setdefault(group, []).append({
                "method": method.upper(), "path": path, "summary": _summary(operation),
                "path_parameters": _parameters(operation, "path", components),
                "query": _parameters(operation, "query", components),
                "body": _body(operation, components),
            })
    return {
        "errors": {"shape": {"detail": {"code": "string", "message": "string"}},
                   "codes": {str(status): code for status, code in CODE_BY_STATUS.items()}},
        "groups": [{"name": name, "routes": sorted(routes, key=lambda r: (r["path"], r["method"]))}
                   for name, routes in sorted(groups.items())],
    }
