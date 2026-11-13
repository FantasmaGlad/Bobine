import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

from app.main import app  # noqa: E402

ATTACHMENTS = {("get", "/api/videos/{video_id}/chapters/export")}


def _success(operation: dict) -> dict:
    responses = operation.get("responses", {})
    return next((responses[code] for code in ("200", "201", "202") if code in responses), {})


def _untyped(schema: dict) -> bool:
    return not schema or (schema.get("type") == "object" and "properties" not in schema and "additionalProperties" not in schema)


@pytest.mark.recent_stack
def test_every_json_operation_declares_its_response():
    missing = []
    for path, operations in app.openapi()["paths"].items():
        for method, operation in operations.items():
            content = _success(operation).get("content", {})
            if "application/json" in content and _untyped(content["application/json"].get("schema", {})):
                missing.append((method, path))
    assert sorted(set(missing) - ATTACHMENTS) == []
