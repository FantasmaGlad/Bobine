"""Forme unique des erreurs de l'API : `{"detail": {"code", "message", ...}}`."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

CODE_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "too_large",
    422: "invalid",
    429: "too_many_requests",
    500: "internal_error",
    503: "unavailable",
    504: "timeout",
    507: "insufficient_storage",
}


def error_body(status: int, detail: object) -> dict:
    if isinstance(detail, dict):
        return {"code": CODE_BY_STATUS.get(status, "error"), "message": "", **detail}
    return {"code": CODE_BY_STATUS.get(status, "error"), "message": "" if detail is None else str(detail)}


async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": error_body(exc.status_code, exc.detail)},
                        headers=getattr(exc, "headers", None))


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", "")} for e in exc.errors()]
    message = " ; ".join(f"{'.'.join(map(str, e['loc'][1:]))} : {e['msg']}".lstrip(" :") for e in errors)
    return JSONResponse(status_code=422, content={"detail": {"code": "invalid", "message": message, "errors": errors}})


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": error_body(500, "Erreur interne du serveur.")})


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled_error)
