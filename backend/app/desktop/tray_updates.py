"""Mises à jour vues du plateau : vérification périodique, état, notifications."""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
import webbrowser
from urllib.parse import urlsplit

import pystray

from app.desktop import system, tray_actions
from app.utils.port import DEFAULT_PORT, read_runtime

from .tray_icon import _detect_current_channel, _load_icon_image
from .tray_supervisor import is_backend_running
from .tray_urls import UPDATE_POLL_INTERVAL_SECONDS, UPDATE_STATUS_POLL_INTERVAL_SECONDS, _updates_check_url, _updates_status_url

logger = logging.getLogger(__name__)


_update_lock = threading.Lock()


_update_state: dict = {"has_update": False, "latest_version": None, "download_url": None}


def _check_for_update_once() -> None:
    try:
        req = urllib.request.Request(_updates_check_url(), headers={"User-Agent": "BobineTray"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        with _update_lock:
            _update_state["has_update"] = bool(data.get("has_update"))
            _update_state["latest_version"] = data.get("latest_version")
            _update_state["download_url"] = data.get("download_url") or data.get("html_url")
        if _update_state["has_update"]:
            logger.info(f"Mise à jour disponible : {_update_state['latest_version']}")
    except Exception as e:
        logger.info(f"Vérification de mise à jour indisponible : {e}")


def _update_poll_loop() -> None:
    deadline = time.time() + 30.0
    while time.time() < deadline and not is_backend_running():
        time.sleep(0.5)
    while True:
        _check_for_update_once()
        time.sleep(UPDATE_POLL_INTERVAL_SECONDS)


def _notify_best_effort(icon: "pystray.Icon", title: str, message: str) -> None:
    try:
        icon.notify(message, title)
    except Exception as e:
        logger.debug(f"Notification native indisponible ({title!r}) : {e}")


def _port_fallback_notice(icon: "pystray.Icon", wait_seconds: float = 120.0) -> None:
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        info = read_runtime()
        if info:
            if info.get("fallback"):
                port, preferred = info["port"], info.get("preferred", DEFAULT_PORT)
                logger.warning("Backend sur le port de repli %s (port %s occupé)", port, preferred)
                _notify_best_effort(
                    icon,
                    "Bobine — port de repli",
                    f"Le port {preferred} est occupé : Bobine écoute sur le port {port}. "
                    f"Autres appareils : http://<adresse>:{port}."
                    + ("" if not system.current().FIREWALL_HINT else f" Si un pare-feu est actif, ouvrez ce port (firewalld : {DEFAULT_PORT} seulement)."),
                )
            return
        time.sleep(1.0)


def _update_status_poll_loop(icon: "pystray.Icon") -> None:
    last_notified_started_at = None
    current_channel = _detect_current_channel()
    while True:
        time.sleep(UPDATE_STATUS_POLL_INTERVAL_SECONDS)
        detected_channel = _detect_current_channel()
        if detected_channel != current_channel:
            current_channel = detected_channel
            try:
                icon.icon = _load_icon_image(detected_channel)
            except Exception as e:
                logger.debug(f"Mise à jour icône tray ({detected_channel}): {e}")

        try:
            req = urllib.request.Request(_updates_status_url(), headers={"User-Agent": "BobineTray"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                status = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue

        step = status.get("step")
        started_at = status.get("started_at")
        if not tray_actions.should_notify_update_outcome(status, last_notified_started_at):
            if step in ("done", "failed"):
                last_notified_started_at = started_at
            continue
        last_notified_started_at = started_at

        if step == "done":
            _notify_best_effort(icon, "Bobine — Mise à jour installée", status.get("message") or "Mise à jour terminée avec succès.")
        else:
            _notify_best_effort(icon, "Bobine — Échec de la mise à jour", status.get("error") or status.get("message") or "La mise à jour a échoué.")


def _on_check_update(icon, item) -> None:
    with _update_lock:
        has_update, download_url = _update_state["has_update"], _update_state["download_url"]
    if has_update and download_url and urlsplit(download_url).scheme in ("http", "https"):
        webbrowser.open(download_url)
    else:
        if has_update and download_url:
            logger.warning("Adresse de mise à jour refusée (schéma non web) : %s", download_url)
        threading.Thread(target=_check_for_update_once, daemon=True, name="bobine-tray-update-check-now").start()


def _update_text(item) -> str:
    with _update_lock:
        if _update_state["has_update"]:
            return f"Mise à jour disponible ({_update_state['latest_version']}) — Télécharger"
        return "Aucune mise à jour disponible (cliquer pour vérifier)"
