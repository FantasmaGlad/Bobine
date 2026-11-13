import logging
import os
import re
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from app.utils._pydantic_compat import OrmModel
from sqlalchemy.orm import Session

from app.api.contract import LOG_LEVELS
from app.config import settings
from app.database import get_db
from app.models import ActivityLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])


class ActivityLogResponse(OrmModel):
    id: int
    timestamp: datetime
    event_type: str
    detail: str | None


LEVELS = LOG_LEVELS
_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) (DEBUG|INFO|WARNING|ERROR|CRITICAL) ([^:\s]+): ?(.*)$")
_MAX_FILE_BYTES = 8 * 1024 * 1024
_ARCHIVES = 5


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_since(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:
        raise HTTPException(status_code=422, detail={
            "code": "invalid_since", "message": "since attend une date ISO 8601 avec fuseau, par exemple 2026-11-05T00:00:00Z.",
        })
    return parsed


def _open_technical_files(stack: ExitStack) -> list[BinaryIO]:
    base = Path(settings.technical_log_path)
    handles = []
    for path in [base, *(base.with_name(f"{base.name}.{i}") for i in range(1, _ARCHIVES + 1))]:
        try:
            handles.append(stack.enter_context(open(path, "rb")))
        except OSError:
            continue
    return handles


def _parse_technical(handle: BinaryIO) -> tuple[list[dict[str, Any]], int]:
    handle.seek(max(0, os.fstat(handle.fileno()).st_size - _MAX_FILE_BYTES))
    text = handle.read().decode("utf-8", errors="replace")
    entries: list[dict[str, Any]] = []
    orphans = 0
    previous: datetime | None = None
    for line in text.splitlines():
        match = _LINE_RE.match(line)
        if match:
            naive = datetime.strptime(f"{match[1]}.{match[2]}", "%Y-%m-%d %H:%M:%S.%f")
            stamp = naive.astimezone()
            if previous is not None and stamp < previous:
                later = naive.replace(fold=1).astimezone()
                if later > previous:
                    stamp = later
            previous = stamp
            entries.append({"time": stamp, "level": match[3].lower(), "category": match[4], "message": match[5]})
        elif entries:
            entries[-1]["message"] += "\n" + line
        elif line.strip():
            orphans += 1
    return entries, orphans


@router.get("")
def read_logs(
    source: str = Query("technical"),
    level: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Journaux en JSON stable, du plus récent au plus ancien."""
    if source not in ("technical", "activity"):
        raise HTTPException(status_code=422, detail={"code": "invalid_source", "message": "source attend technical ou activity."})
    if level is not None and level not in LEVELS:
        raise HTTPException(status_code=422, detail={"code": "invalid_level", "message": f"level attend l'un de : {', '.join(LEVELS)}."})
    threshold = LEVELS.index(level) if level else 0
    start = _parse_since(since)
    entries: list[dict[str, Any]] = []
    truncated = False
    skipped = 0
    if source == "activity":
        if threshold > LEVELS.index("info"):
            rows = []
        else:
            query = db.query(ActivityLog).order_by(ActivityLog.id.desc())
            if start is not None:
                query = query.filter(ActivityLog.timestamp >= start.astimezone(timezone.utc).replace(tzinfo=None))
            rows = query.limit(limit + 1).all()
        truncated = len(rows) > limit
        for row in rows[:limit]:
            stamp = row.timestamp if row.timestamp.tzinfo else row.timestamp.replace(tzinfo=timezone.utc)
            entries.append({"timestamp": _utc_iso(stamp), "level": "info", "category": row.event_type, "message": row.detail or ""})
    else:
        done = False
        with ExitStack() as stack:
            for handle in _open_technical_files(stack):
                parsed, orphans = _parse_technical(handle)
                skipped += orphans
                for entry in reversed(parsed):
                    if start is not None and entry["time"] < start:
                        done = True
                        break
                    if LEVELS.index(entry["level"]) < threshold:
                        continue
                    if len(entries) == limit:
                        truncated = done = True
                        break
                    entries.append({"timestamp": _utc_iso(entry["time"]), "level": entry["level"],
                                    "category": entry["category"], "message": entry["message"]})
                if done:
                    break
    return {
        "schema": 1,
        "generated_at": _utc_iso(datetime.now(timezone.utc)),
        "source": source,
        "filters": {"level": level, "since": since, "limit": limit},
        "count": len(entries),
        "truncated": truncated,
        "skipped_unparsed": skipped,
        "entries": entries,
    }


@router.get("/activity", response_model=List[ActivityLogResponse])
def list_activity_logs(
    event_type: str | None = None,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
):
    """Log d'activité filtrable."""
    query = db.query(ActivityLog).order_by(ActivityLog.id.desc())
    if event_type:
        query = query.filter(ActivityLog.event_type == event_type)
    return query.limit(limit).all()


@router.get("/activity/event-types", response_model=List[str])
def list_activity_event_types(db: Session = Depends(get_db)):
    rows = db.query(ActivityLog.event_type).distinct().all()
    return sorted({r[0] for r in rows})


@router.get("/technical", response_class=PlainTextResponse)
def get_technical_log(lines: int = Query(500, le=5000)):
    """Log technique brut : erreurs backend, échecs de lecture, etc."""
    log_path = settings.technical_log_path
    if not log_path.exists():
        return ""
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.readlines()
    return "".join(content[-lines:])


@router.get("/technical/download")
def download_technical_log():
    """Téléchargement du log technique complet."""
    from fastapi.responses import FileResponse

    log_path = settings.technical_log_path
    if not log_path.exists():
        return PlainTextResponse("", media_type="text/plain")
    return FileResponse(log_path, filename="bobine-technical.log", media_type="text/plain")


@router.delete("/activity")
def delete_activity_logs(
    ids: List[int] | None = Query(None),
    limit: int | None = Query(None, gt=0),
    db: Session = Depends(get_db),
):
    """Supprime des logs d'activité : par identifiants précis (sélection dans le tableau), les `limit` plus récents (purge), ou tout si aucun des deux n'est fourni (bouton "vider")."""
    if ids:
        deleted = db.query(ActivityLog).filter(ActivityLog.id.in_(ids)).delete(synchronize_session=False)
    elif limit:
        recent_ids = [
            row.id for row in db.query(ActivityLog.id).order_by(ActivityLog.id.desc()).limit(limit).all()
        ]
        deleted = (
            db.query(ActivityLog).filter(ActivityLog.id.in_(recent_ids)).delete(synchronize_session=False)
            if recent_ids else 0
        )
    else:
        deleted = db.query(ActivityLog).delete(synchronize_session=False)
    db.commit()
    return {"message": f"{deleted} entrée(s) supprimée(s)", "deleted": deleted}


@router.delete("/technical")
def clear_technical_log():
    """Vide le log technique."""
    log_path = settings.technical_log_path
    if log_path.exists():
        log_path.write_text("", encoding="utf-8")
    return {"message": "Log technique vidé"}
