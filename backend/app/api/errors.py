"""Forme unique des erreurs de l'API : `{"detail": ...}`, comme les `HTTPException` levées par les routes."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    # La trace est déjà journalisée par le serveur ASGI, qui relève l'exception après cette réponse.
    return JSONResponse(status_code=500, content={"detail": "Erreur interne du serveur."})


def install_error_handlers(app: FastAPI) -> None:
    """Une exception non prévue par une route répond en JSON, jamais en texte brut."""
    app.add_exception_handler(Exception, _unhandled_error)
