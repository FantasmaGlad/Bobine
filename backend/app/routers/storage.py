"""API « Stockage externe » (`/api/storage/*`) : supports amovibles, appareils portables, bibliothèque externe, longévité.

Contrôle d'accès IDENTIQUE à celui des périphériques (`routers/devices.py::require_access`) : fonction désactivée par
défaut (403), écran local de confiance, PIN pour tout autre appareil (403 `pin_not_set`, 401 `pin_required`).
Les erreurs sont toujours structurées `{"detail": {"code", "message", ...}}` : aucune erreur d'OS ne devient une 500,
et aucun chemin hors des volumes montés n'est jamais exposé (le client n'envoie que des chemins RELATIFS au support).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Awaitable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.devices import security
from app.devices.base import DeviceError
from app.routers.devices import Access, _client_ip, _fail, _get_setting, _locked, require_access
from app.storage import fsadvisor
from app.storage.formatting.refusals import FormatRefusal
from app.storage.paths import PathError
from app.utils.activity_log import log_activity
from app.storage.service import service
from app.storage.transfer import TransferError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/storage", tags=["storage"])

T = TypeVar("T")
_KEY = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _key(key: str) -> str:
    if not _KEY.fullmatch(key):
        raise _fail(404, "volume_not_found", "Support introuvable.")
    return key


async def _guard(coro: Awaitable[T]) -> T:
    """Convertit toute erreur (pilote, chemin, transfert) en réponse structurée ; jamais de 500."""
    try:
        return await coro
    except DeviceError as exc:
        raise _fail(exc.status, exc.code, exc.message, **getattr(exc, "extra", {})) from exc
    except PathError as exc:
        raise _fail(exc.status, exc.code, exc.message) from exc
    except TransferError as exc:
        raise _fail(exc.status, exc.code, exc.message, **exc.extra) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Erreur inattendue du stockage externe : %s", exc, exc_info=True)
        raise _fail(502, "driver_error", "Le système n'a pas pu exécuter cette opération.") from exc


class MountRequest(BaseModel):
    mode: str = "ro"


class Selection(BaseModel):
    path: str = Field(max_length=4096)


class TransferRequest(BaseModel):
    entries: list[Selection] = Field(max_length=500)
    kind: str
    force: bool = False


class ExportRequest(BaseModel):
    kind: str
    ids: list[int] = Field(max_length=2000)
    dest: str | None = Field(default=None, max_length=1024)


class LibraryRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=60)


class SettingsRequest(BaseModel):
    read_only: bool | None = None
    noatime: bool | None = None
    noexec: bool | None = None
    standby_minutes: int | None = None
    smart_monitor: bool | None = None
    auto_mount_library: bool | None = None

    def values(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


@router.get("/status")
async def status(_: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.status())


@router.get("/volumes")
async def volumes(_: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.list_volumes())


@router.post("/volumes/{key}/mount")
async def mount(key: str, payload: MountRequest, _: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.mount(_key(key), payload.mode))


@router.post("/volumes/{key}/unmount")
async def unmount(key: str, _: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.unmount(_key(key)))


@router.post("/volumes/{key}/eject")
async def eject(key: str, _: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.eject(_key(key)))


@router.get("/volumes/{key}/browse")
async def browse(
    key: str,
    path: str = Query("", max_length=4096),
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    show_hidden: bool = False,
    media_only: bool = False,
    _: Access = Depends(require_access),
) -> dict[str, Any]:
    return await _guard(service.browse(_key(key), path, offset, limit, show_hidden, media_only))


@router.post("/volumes/{key}/import", status_code=202)
async def start_import(key: str, payload: TransferRequest, _: Access = Depends(require_access)) -> dict[str, Any]:
    """Copie vérifiée vers le stockage local puis importeur existant ; suivi par `GET /api/import-jobs`."""
    entries = [{"path": e.path} for e in payload.entries]
    return await _guard(service.start_import(_key(key), entries, payload.kind, payload.force))


@router.post("/volumes/{key}/index", status_code=202)
async def start_index(key: str, payload: TransferRequest, _: Access = Depends(require_access)) -> dict[str, Any]:
    """« Utiliser comme extension » : indexe les médias sélectionnés sans les copier (lecture directe, lecture seule)."""
    entries = [{"path": e.path} for e in payload.entries]
    return await _guard(service.start_index(_key(key), entries, payload.kind))


@router.post("/volumes/{key}/export", status_code=202)
async def start_export(key: str, payload: ExportRequest, _: Access = Depends(require_access)) -> dict[str, Any]:
    """Copie de médias locaux vers le support : remontage en écriture temporaire et explicite, puis retour en lecture seule."""
    return await _guard(service.start_export(_key(key), payload.kind, payload.ids, payload.dest))


@router.post("/volumes/{key}/library")
async def register_library(key: str, payload: LibraryRequest, _: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.register_library(_key(key), payload.nickname))


@router.delete("/volumes/{key}/library")
async def unregister_library(key: str, purge: bool = False, _: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.unregister_library(_key(key), purge))


@router.get("/volumes/{key}/health")
async def health(key: str, refresh: bool = False, _: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.health(_key(key), refresh))


@router.post("/volumes/{key}/trim")
async def trim(key: str, _: Access = Depends(require_access)) -> dict[str, str]:
    return await _guard(service.trim(_key(key)))


@router.put("/volumes/{key}/settings")
async def update_volume_settings(key: str, payload: SettingsRequest, _: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.update_settings(_key(key), payload.values()))


@router.put("/settings")
async def update_default_settings(payload: SettingsRequest, _: Access = Depends(require_access)) -> dict[str, Any]:
    """Valeurs par défaut des réglages de longévité (supports non enregistrés et nouveaux supports)."""
    return await _guard(service.update_settings(None, payload.values()))


@router.get("/advisor/format")
async def advisor_format(
    host: str = "linux",
    others: str = "",
    media: str = "flash",
    legacy: bool = False,
    _: Access = Depends(require_access),
) -> dict[str, Any]:
    """Système de fichiers conseillé selon l'OS hôte et les OS qui brancheront le support. Ne formate JAMAIS."""
    other_oses = tuple(o for o in others.split(",") if o)
    return fsadvisor.recommend_format(host, other_oses, media, legacy_readers=legacy)


@router.get("/portable")
async def portable(_: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.portable())


@router.post("/portable/{device_id}/mount")
async def portable_mount(device_id: str, _: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.portable_mount(_key(device_id)))


@router.post("/portable/{device_id}/unmount")
async def portable_unmount(device_id: str, _: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.portable_unmount(_key(device_id)))


# ---------------------------------------------------------------------------
# Assistant de formatage : plan (lecture seule) puis exécution (jeton, confirmation, PIN, cascade de vérifications)
# ---------------------------------------------------------------------------


class FormatPlanRequest(BaseModel):
    key: str = Field(max_length=80)
    travels: list[str] = Field(default_factory=list, max_length=4)   # OS qui brancheront aussi le support (windows, macos, android)


class FormatExecuteRequest(BaseModel):
    key: str = Field(max_length=80)
    token: str | None = Field(default=None, max_length=200)
    fs: str = Field(max_length=16)
    label: str = Field(max_length=80)
    confirm: str = Field(default="", max_length=200)
    acknowledged: bool = False
    pin: str | None = Field(default=None, max_length=32)


def _require_format_pin(request: Request, db: Session, pin: str | None) -> None:
    """Dès qu'un PIN existe, TOUT formatage l'exige, y compris depuis l'écran local de confiance (jamais journalisé)."""
    stored = _get_setting(db, security.SETTING_PIN_HASH)
    if not stored:
        raise _fail(403, "format_pin_not_set", "Définissez un code PIN depuis l’écran local avant de formater un support.")
    ip = _client_ip(request)
    retry = security.rate_limiter.retry_after(ip)
    if retry:
        raise _locked(retry)
    if not pin:
        raise _fail(401, "format_pin_required", "Saisissez le code PIN d'administration pour formater.")
    if not security.verify_pin(pin, stored):
        lockout = security.rate_limiter.register_failure(ip)
        log_activity(db, "storage_format_refused", f"format_pin_invalid (IP {ip})")
        if lockout:
            raise _locked(lockout)
        raise _fail(401, "format_pin_invalid", "Code PIN incorrect.", attempts_left=security.rate_limiter.attempts_left(ip))
    security.rate_limiter.register_success(ip)


@router.post("/format/plan")
async def format_plan(payload: FormatPlanRequest, access: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Plan de formatage : n'écrit RIEN. Renvoie ce qui sera effacé, les formats possibles et un jeton court à usage unique."""
    pin_required = bool(_get_setting(db, security.SETTING_PIN_HASH))
    return await _guard(service.formatter.plan(_key(payload.key), owner=access.ip, travels=payload.travels, pin_required=pin_required))


@router.post("/format/execute", status_code=202)
async def format_execute(payload: FormatExecuteRequest, request: Request, access: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_format_pin(request, db, payload.pin)
    return await _guard(service.formatter.start(
        _key(payload.key), token=payload.token, fs=payload.fs, label=payload.label, confirm_text=payload.confirm,
        acknowledged=payload.acknowledged, owner=access.ip,
    ))


@router.get("/format/active")
async def format_active(_: Access = Depends(require_access)) -> dict[str, Any]:
    job = service.formatter.active()
    return {"job": job.public() if job else None}


@router.get("/format/jobs/{job_id}")
async def format_job(job_id: str, _: Access = Depends(require_access)) -> dict[str, Any]:
    if not _KEY.fullmatch(job_id):
        raise _fail(404, "format_job_not_found", "Opération introuvable.")
    return await _guard(_sync(lambda: service.formatter.job(job_id).public()))


@router.delete("/format/jobs/{job_id}")
async def format_cancel(job_id: str, _: Access = Depends(require_access)) -> dict[str, Any]:
    """Annule AVANT le point de non-retour (aucun effacement n'a eu lieu) ; refusé ensuite."""
    if not _KEY.fullmatch(job_id):
        raise _fail(404, "format_job_not_found", "Opération introuvable.")
    return await _guard(_sync(lambda: service.formatter.cancel(job_id)))


async def _sync(fn: Any) -> Any:
    return fn()
