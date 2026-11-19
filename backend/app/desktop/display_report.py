"""Rapport de l'état des écrans au backend."""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from typing import Callable

from app.desktop import system


logger = logging.getLogger(__name__)


_report_generation = 0


_report_lock = threading.Lock()


def _source_label() -> str:
    return system.current().SOURCE_LABEL


def _resolve_url(url: "str | Callable[[], str]") -> str:
    return url() if callable(url) else url


def report_display_state(
    state_url: "str | Callable[[], str]",
    count: int,
    resolution: str | None = None,
    *,
    source: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    urlopen=urllib.request.urlopen,
    max_attempts: int = 60,
) -> bool:
    """`PUT /api/display/state` avec nouvelles tentatives (backend pas encore prêt au démarrage)."""
    global _report_generation
    with _report_lock:
        _report_generation += 1
        generation = _report_generation
    body = {"external_count": int(count), "source": source or _source_label()}
    if resolution:
        body["resolution"] = resolution
    payload = json.dumps(body).encode("utf-8")
    for attempt in range(max_attempts):
        if generation != _report_generation:
            return False
        try:
            request = urllib.request.Request(
                _resolve_url(state_url), data=payload, method="PUT",
                headers={"Content-Type": "application/json", "User-Agent": "BobineTray"},
            )
            with urlopen(request, timeout=5) as response:
                if 200 <= response.status < 300:
                    return True
        except Exception as exc:
            logger.debug(f"Rapport d'état des écrans en échec (tentative {attempt + 1}) : {exc}")
        sleep(min(1.0 * (attempt + 1), 10.0))
    return False
