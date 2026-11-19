"""Intégration au système : agent de lancement macOS, raccourci de bureau."""

from __future__ import annotations

import logging

from app.desktop import system

logger = logging.getLogger(__name__)


def _ensure_launch_agent_macos() -> None:
    system.current().ensure_launch_agent()


def _ensure_desktop_shortcut() -> None:
    try:
        system.current().ensure_desktop_shortcut()
    except Exception as e:
        logger.debug(f"Vérification du raccourci Bureau ignorée : {e!r}")
