"""Chapitres d'un cours : lecture (JSON, WebVTT, liste « 05:00 Titre », chapitres
incorporés au fichier), validation et sérialisation.

Un chapitre est `{"start_seconds", "end_seconds", "title"}`. `end_seconds` vaut
le début du chapitre suivant (ou la durée du cours) quand il n'est pas fourni.
Module sans dépendance sur la base : testable seul.
"""

import json
import re
import subprocess
from typing import Any

from app.utils.ffmpeg_binaries import FFPROBE_BIN, media_subprocess_kwargs

MAX_CHAPTERS = 200
MAX_TITLE_LENGTH = 120
MAX_CHAPTER_BYTES = 256 * 1024
_FFPROBE_TIMEOUT_SECONDS = 30

_TIMESTAMP = re.compile(r"^\s*(?:(\d+):)?(\d{1,3}):(\d{2})(?:[.,](\d{1,3}))?\s*$")
_TEXT_LINE = re.compile(r"^\s*(?:\[)?(\d{1,2}:)?\d{1,3}:\d{2}(?:[.,]\d{1,3})?(?:\])?\s*[-–—:.)]*\s*(.+?)\s*$")
_TEXT_TIME = re.compile(r"^\s*\[?((?:\d{1,2}:)?\d{1,3}:\d{2}(?:[.,]\d{1,3})?)\]?")


class ChapterError(ValueError):
    """Fichier de chapitres illisible ou incohérent (message affichable)."""


def parse_timestamp(value: Any) -> float:
    """Secondes depuis `90`, `"90"`, `"1:30"`, `"01:02:03"` ou `"00:05.500"`."""
    if isinstance(value, bool):
        raise ChapterError("Horodatage invalide.")
    if isinstance(value, (int, float)):
        seconds = float(value)
    else:
        text = str(value).strip()
        match = _TIMESTAMP.match(text)
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2))
            secs = int(match.group(3))
            millis = float(f"0.{match.group(4)}") if match.group(4) else 0.0
            seconds = hours * 3600 + minutes * 60 + secs + millis
        else:
            try:
                seconds = float(text.replace(",", "."))
            except ValueError as exc:
                raise ChapterError(f"Horodatage invalide : « {text[:30]} ».") from exc
    if seconds != seconds or seconds < 0 or seconds > 24 * 3600 * 7:
        raise ChapterError("Horodatage hors limites.")
    return round(seconds, 3)


def _pick_title(raw: Any) -> str:
    """Titre d'un chapitre, éventuellement localisé (`{"fr": "...", "en": "..."}`)."""
    if isinstance(raw, dict):
        for key in ("fr", "en"):
            if raw.get(key):
                raw = raw[key]
                break
        else:
            raw = next((v for v in raw.values() if v), "")
    return str(raw or "").strip()


def parse_json(text: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ChapterError(f"JSON invalide : {exc.msg} (ligne {exc.lineno}).") from exc
    items = data.get("chapters") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ChapterError("Le fichier doit contenir une liste « chapters ».")
    parsed: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ChapterError(f"Chapitre {index} : objet attendu.")
        start = next((item[k] for k in ("start", "start_seconds", "time", "t") if k in item), None)
        if start is None:
            raise ChapterError(f"Chapitre {index} : début manquant (« start »).")
        end = next((item[k] for k in ("end", "end_seconds") if k in item and item[k] not in (None, "")), None)
        parsed.append(
            {
                "start_seconds": parse_timestamp(start),
                "end_seconds": parse_timestamp(end) if end is not None else None,
                "title": _pick_title(item.get("title", item.get("name"))),
            }
        )
    return parsed


def parse_vtt(text: str) -> list[dict[str, Any]]:
    """WebVTT de type `chapters` : un repère `début --> fin` suivi du titre."""
    parsed: list[dict[str, Any]] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    for block in blocks:
        lines = [line for line in block.split("\n") if line.strip()]
        for position, line in enumerate(lines):
            if "-->" in line:
                start_text, _, end_text = line.partition("-->")
                title = " ".join(lines[position + 1 :]).strip()
                parsed.append(
                    {
                        "start_seconds": parse_timestamp(start_text.strip().split()[0]),
                        "end_seconds": parse_timestamp(end_text.strip().split()[0]),
                        "title": re.sub(r"<[^>]+>", "", title),
                    }
                )
                break
    return parsed


def parse_text(text: str) -> list[dict[str, Any]]:
    """Liste copiée-collée : `00:00 Introduction`, `[05:30] - Cardio`, `1:02:10 Étirements`."""
    parsed: list[dict[str, Any]] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if not line.strip():
            continue
        time_match = _TEXT_TIME.match(line)
        line_match = _TEXT_LINE.match(line)
        if not time_match or not line_match:
            raise ChapterError(f"Ligne non reconnue : « {line.strip()[:40]} » (attendu : « 05:00 Titre »).")
        parsed.append({"start_seconds": parse_timestamp(time_match.group(1)), "end_seconds": None, "title": line_match.group(2)})
    return parsed


def parse_any(text: str, filename: str = "") -> list[dict[str, Any]]:
    """Choisit le lecteur d'après le contenu (le nom de fichier n'est qu'un indice)."""
    stripped = text.lstrip("﻿").strip()
    if not stripped:
        raise ChapterError("Fichier vide.")
    lowered = filename.lower()
    if stripped.startswith(("{", "[")) or lowered.endswith(".json"):
        return parse_json(stripped)
    if stripped.upper().startswith("WEBVTT") or lowered.endswith(".vtt"):
        return parse_vtt(stripped)
    return parse_text(stripped)


def normalize(chapters: list[dict[str, Any]], duration_seconds: float | None) -> list[dict[str, Any]]:
    """Trie, valide (titres, bornes, doublons) et complète les fins manquantes."""
    if len(chapters) > MAX_CHAPTERS:
        raise ChapterError(f"{MAX_CHAPTERS} chapitres au maximum.")
    ordered = sorted(chapters, key=lambda item: item["start_seconds"])
    result: list[dict[str, Any]] = []
    for index, item in enumerate(ordered, start=1):
        title = (item.get("title") or "").strip()
        if not title:
            raise ChapterError(f"Chapitre {index} : titre manquant.")
        start = float(item["start_seconds"])
        if duration_seconds and start > duration_seconds + 1:
            raise ChapterError(f"Chapitre « {title[:40]} » : début ({start:.0f} s) après la fin du cours ({duration_seconds:.0f} s).")
        if result and abs(start - result[-1]["start_seconds"]) < 0.001:
            raise ChapterError(f"Deux chapitres commencent à la même seconde ({start:.0f} s).")
        result.append({"start_seconds": start, "end_seconds": item.get("end_seconds"), "title": title[:MAX_TITLE_LENGTH]})
    for index, item in enumerate(result):
        following = result[index + 1]["start_seconds"] if index + 1 < len(result) else duration_seconds
        end = item["end_seconds"]
        if end is None or (following is not None and end > following):
            end = following
        if end is not None and end <= item["start_seconds"]:
            end = None
        item["end_seconds"] = end
    return result


def read_embedded(file_path: str) -> list[dict[str, Any]]:
    """Chapitres incorporés au conteneur (MKV, MP4) ; liste vide s'il n'y en a pas."""
    try:
        completed = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-print_format", "json", "-show_chapters", file_path],
            capture_output=True,
            text=True,
            timeout=_FFPROBE_TIMEOUT_SECONDS,
            check=True,
            **media_subprocess_kwargs(),
        )
        data = json.loads(completed.stdout or "{}")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []
    chapters = []
    for item in data.get("chapters", []):
        title = (item.get("tags") or {}).get("title") or f"Chapitre {len(chapters) + 1}"
        try:
            chapters.append(
                {
                    "start_seconds": round(float(item["start_time"]), 3),
                    "end_seconds": round(float(item["end_time"]), 3) if item.get("end_time") else None,
                    "title": title,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return chapters
