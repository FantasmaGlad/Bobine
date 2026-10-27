"""Contrat HTTP du stockage sous FastAPI/Pydantic Android et bureau.

Importer l'application complète détecte aussi les modèles des autres routeurs.
Seule la frontière pilote est simulée : ni disque réel ni privilège nécessaire.
"""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import storage


@pytest.fixture()
def client(monkeypatch):
    async def allowed():
        return None

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[storage.require_access] = allowed
    fake = AsyncMock()
    fake.status.return_value = {"supported": False, "reason": "unsupported_platform"}
    fake.update_settings.return_value = {"noexec": False}
    fake.start_import.return_value = {"job_id": 42}
    monkeypatch.setattr(storage, "service", fake)
    monkeypatch.setattr("app.main.storage_service", fake)
    try:
        with TestClient(app, raise_server_exceptions=True) as http:
            yield http, fake
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_storage_status_and_partial_settings(client):
    http, fake = client
    assert http.get("/api/storage/status").json() == {"supported": False, "reason": "unsupported_platform"}
    result = http.put("/api/storage/settings", json={"noexec": False})
    assert result.status_code == 200 and result.json() == {"noexec": False}
    fake.update_settings.assert_awaited_once_with(None, {"noexec": False})


def test_storage_transfer_list_is_decoded_and_limited(client):
    http, fake = client
    route = "/api/storage/volumes/u-test/import"
    response = http.post(route, json={"entries": [{"path": "Cours/a.mp4"}], "kind": "video"})
    assert response.status_code == 202 and response.json() == {"job_id": 42}
    fake.start_import.assert_awaited_once_with("u-test", [{"path": "Cours/a.mp4"}], "video", False)
    response = http.post(route, json={"entries": [{"path": "a"}] * 501, "kind": "video"})
    assert response.status_code == 422
    assert fake.start_import.await_count == 1
    response = http.post("/api/storage/volumes/u-test/export", json={"ids": list(range(2001)), "kind": "video"})
    assert response.status_code == 422
    fake.start_export.assert_not_awaited()


def test_storage_openapi_exposes_list_limits():
    schema = app.openapi()["components"]["schemas"]
    assert schema["TransferRequest"]["properties"]["entries"]["maxItems"] == 500
    assert schema["ExportRequest"]["properties"]["ids"]["maxItems"] == 2000


def test_openapi_has_unique_operation_ids_and_keeps_head_routes():
    from app.main import app
    schema = app.openapi()
    operations = [operation["operationId"] for path in schema["paths"].values()
                  for operation in path.values() if isinstance(operation, dict) and "operationId" in operation]
    assert len(operations) == len(set(operations))
    for path in ("/api/videos/{video_id}/stream", "/api/backgrounds/{background_id}/stream",
                 "/api/audio/tracks/{track_id}/stream", "/api/radio/tracks/{track_id}/stream",
                 "/api/radio/tracks/{track_id}/cover", "/api/radio/announcements/{announcement_id}/stream"):
        assert "get" in schema["paths"][path]
        assert "head" not in schema["paths"][path]
        assert any(getattr(route, "path", None) == path and "HEAD" in getattr(route, "methods", set()) for route in app.routes)
