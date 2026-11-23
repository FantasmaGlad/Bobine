"""Icône et menu du plateau : canal courant, sorties d'affichage, actions."""

from __future__ import annotations

import webbrowser

import pystray

from app.desktop import tray_actions
from app.quick_actions import QUICK_ACTIONS
from app.desktop.displays import DisplayOrchestrator, DisplayWatcher

from .tray_display import launch_kiosk_browser
from .tray_supervisor import BackendSupervisor
from .tray_updates import _notify_best_effort, _on_check_update, _update_text
from .tray_urls import _admin_url


def _output_items(controls: "tray_actions.Controls") -> list:
    def item_for(kind: str, target: str, name: str) -> "pystray.MenuItem":
        def on_click(icon, item):
            if not controls.toggle(kind, target):
                _notify_best_effort(icon, "Bobine", f"{name} : rien à mettre en pause ni à reprendre.")

        return pystray.MenuItem(
            lambda item: controls.label(kind, target, name), on_click,
            enabled=lambda item: controls.next_action(controls.states().get((kind, target))) is not None,
        )

    def on_stop_all(icon, item):
        accepted = controls.stop_all()
        if accepted < len(tray_actions.TARGETS):
            _notify_best_effort(icon, "Bobine", f"Diffusion arrêtée sur {accepted} sortie(s) sur {len(tray_actions.TARGETS)}.")

    return [*[item_for(kind, target, name) for kind, target, name in tray_actions.TARGETS],
            pystray.MenuItem("Couper la diffusion", on_stop_all)]


def _build_menu(supervisor: BackendSupervisor, orchestrator: DisplayOrchestrator, watcher: DisplayWatcher) -> "pystray.Menu":
    def on_reopen_projector(icon, item):
        if not orchestrator.reopen_projector():
            _notify_best_effort(icon, "Bobine", "Aucun écran externe détecté.")

    def on_quit(icon, item):
        watcher.stop()
        orchestrator.shutdown()
        supervisor.stop()
        icon.stop()

    def opener(path):
        return lambda icon, item: webbrowser.open(_admin_url() + path)

    return pystray.Menu(
        pystray.MenuItem(lambda item: "État : en ligne" if supervisor.is_running() else "État : hors ligne", None, enabled=False),
        pystray.Menu.SEPARATOR,
        *_output_items(tray_actions.Controls(_admin_url)),
        pystray.Menu.SEPARATOR,
        *[pystray.MenuItem(action.name, opener(action.path), default=action.path == "/") for action in QUICK_ACTIONS],
        pystray.MenuItem("Ouvrir en mode kiosque", lambda icon, item: launch_kiosk_browser()),
        pystray.MenuItem("Rouvrir l'écran projecteur", on_reopen_projector),
        pystray.MenuItem(_update_text, _on_check_update),
        pystray.MenuItem("Redémarrer", lambda icon, item: supervisor.restart_now()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quitter", on_quit),
    )
