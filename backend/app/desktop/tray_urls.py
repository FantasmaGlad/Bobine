"""Adresses du backend local suivies par le plateau, d'après le port réellement publié, et cadences de surveillance."""

from __future__ import annotations

import logging

from app.outputs import WIRED_OUTPUT
from app.utils.port import DEFAULT_PORT

logger = logging.getLogger(__name__)


def _admin_port() -> int:
    try:
        from app.utils.port import current_port
        return int(current_port())
    except Exception as exc:
        logger.debug("Port publié illisible, port par défaut %s : %s", DEFAULT_PORT, exc)
        return DEFAULT_PORT


def _admin_url() -> str:
    return f"http://127.0.0.1:{_admin_port()}"


def _kiosk_url() -> str:
    return f"{_admin_url()}/kiosk"


def _grid_url() -> str:
    return f"{_admin_url()}/grid"


def _health_url() -> str:
    return f"{_admin_url()}/api/health"


def _display_state_url() -> str:
    return f"{_admin_url()}/api/display/state"


def _projector_url() -> str:
    return f"{_admin_url()}/screen/?output={WIRED_OUTPUT.id}"


def _updates_check_url() -> str:
    return f"{_admin_url()}/api/updates/check"


def _updates_status_url() -> str:
    return f"{_admin_url()}/api/updates/status"


HEALTH_POLL_INTERVAL_SECONDS = 30


HEALTH_FAILURES_BEFORE_RESTART = 3


UPDATE_POLL_INTERVAL_SECONDS = 6 * 60 * 60


UPDATE_STATUS_POLL_INTERVAL_SECONDS = 15
