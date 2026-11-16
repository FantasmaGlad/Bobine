"""Pistes de sous-titres : réception, conversion en WebVTT, enregistrement et suppression."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import VideoSubtitle
from app.utils.subtitles import (
    LANGUAGE_MAP,
    MAX_SUBTITLE_BYTES,
    convert_srt_to_vtt,
    detect_language_from_filename,
    get_subtitles_directory,
    normalize_language_code,
    normalize_language_label,
)

logger = logging.getLogger(__name__)


class SubtitleRejected(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _write_vtt(name: str, content: str) -> Path:
    out_path = get_subtitles_directory() / name
    out_path.write_text(content, encoding="utf-8")
    return out_path


def _store(db: Session, video_id: int, code: str, label: str, path: Path) -> VideoSubtitle:
    sub = VideoSubtitle(video_id=video_id, language_code=code, language_label=label, file_path=str(path.resolve()), format="vtt")
    db.add(sub)
    db.commit()
    return sub


def attach_imported_subtitle(db: Session, video_id: int, temp_path: str, original_name: str) -> None:
    """Sous-titre joint à un import : langue déduite du nom, WebVTT conservé tel quel."""
    code, label = detect_language_from_filename(original_name)
    raw = Path(temp_path).read_text(encoding="utf-8", errors="replace")
    is_vtt = original_name.lower().endswith(".vtt") or raw.lstrip().startswith("WEBVTT")
    path = _write_vtt(f"{video_id}_{code}_{uuid.uuid4().hex[:8]}.vtt", raw if is_vtt else convert_srt_to_vtt(raw))
    _store(db, video_id, code, label, path)


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1", errors="replace")


def save_uploaded_subtitle(db: Session, video_id: int, filename: str, content: bytes, language_code: str | None, language_label: str | None) -> VideoSubtitle:
    if Path(filename).suffix.lower() not in (".srt", ".vtt"):
        raise SubtitleRejected(422, "Seuls les formats .srt et .vtt sont acceptés.")
    if len(content) > MAX_SUBTITLE_BYTES:
        raise SubtitleRejected(413, "Fichier de sous-titres trop volumineux (2 Mo maximum).")
    detected_code, detected_label = detect_language_from_filename(filename)
    code = normalize_language_code(language_code or detected_code)
    if code is None:
        raise SubtitleRejected(422, "Code de langue invalide (ex. fr, en, pt-br).")
    label = normalize_language_label(language_label, LANGUAGE_MAP.get(code, detected_label))
    path = _write_vtt(f"video_{video_id}_{code}_{uuid.uuid4().hex[:8]}.vtt", convert_srt_to_vtt(_decode(content)))
    sub = _store(db, video_id, code, label, path)
    db.refresh(sub)
    return sub


def delete_subtitle(db: Session, sub: VideoSubtitle) -> None:
    path = Path(sub.file_path)
    if path.exists():
        try:
            path.unlink()
        except Exception as exc:
            logger.warning("Impossible de supprimer le fichier VTT %s : %s", path, exc)
    db.delete(sub)
    db.commit()
