"""Surveillance des écrans et orchestration du projecteur quand ils changent."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Sequence
from .display_report import report_display_state
from .monitors import Monitor, external_monitors, list_monitors
from .projector import ProjectorWindow

logger = logging.getLogger(__name__)


POLL_INTERVAL_SECONDS = 2.0


STABLE_POLLS_REQUIRED = 2


REPORT_REFRESH_SECONDS = 60.0


class DisplayWatcher(threading.Thread):
    """Interroge la topologie des moniteurs et appelle `on_change(monitors)` à la première lecture stable puis à chaque changement stable."""

    def __init__(
        self,
        on_change: Callable[[tuple[Monitor, ...]], None],
        list_fn: Callable[[], Sequence[Monitor]] = list_monitors,
        interval: float = POLL_INTERVAL_SECONDS,
        stable_polls: int = STABLE_POLLS_REQUIRED,
    ) -> None:
        super().__init__(daemon=True, name="bobine-display-watcher")
        self._on_change = on_change
        self._list_fn = list_fn
        self._interval = interval
        self._stable_polls = max(1, stable_polls)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def poll_once(self, state: dict) -> None:
        """Un tour de sondage (séparé de `run` pour être testable)."""
        try:
            current = tuple(self._list_fn())
        except Exception as exc:
            logger.warning(f"Sondage des moniteurs en échec : {exc}")
            return
        if current == state.get("candidate"):
            state["count"] = state.get("count", 0) + 1
        else:
            state["candidate"] = current
            state["count"] = 1
        if state["count"] >= self._stable_polls and current != state.get("confirmed"):
            state["confirmed"] = current
            self._on_change(current)

    def run(self) -> None:
        state: dict = {}
        while not self._stop_event.is_set():
            self.poll_once(state)
            self._stop_event.wait(self._interval)


class DisplayOrchestrator:
    """Relie surveillance, rapport au backend et fenêtre projecteur."""

    BACKEND_WAIT_SECONDS = 60.0

    def __init__(
        self,
        state_url: "str | Callable[[], str]",
        projector: ProjectorWindow,
        reporter: Callable[..., bool] = report_display_state,
        ready_check: Callable[[], bool] = lambda: True,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._state_url = state_url
        self._projector = projector
        self._reporter = reporter
        self._ready_check = ready_check
        self._sleep = sleep
        self._last_externals: tuple[Monitor, ...] = ()
        self._generation = 0
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    def _spawn(self, target, *args, name: str) -> None:
        thread = threading.Thread(target=target, args=args, daemon=True, name=name)
        self._threads = [t for t in self._threads if t.is_alive()] + [thread]
        thread.start()

    def join(self, timeout: float = 5.0) -> None:
        """Attend la fin des tâches en cours (tests)."""
        for thread in list(self._threads):
            thread.join(timeout)

    def handle_change(self, monitors: Sequence[Monitor]) -> None:
        externals = tuple(external_monitors(monitors))
        self._last_externals = externals
        self._generation += 1
        logger.info(f"Topologie des écrans : {len(monitors)} moniteur(s), {len(externals)} externe(s)")
        resolution = externals[0].resolution if externals else None
        self._spawn(self._reporter, self._state_url, len(externals), resolution, name="bobine-display-report")
        self._spawn(self._apply, self._generation, externals, name="bobine-display-apply")

    def _apply(self, generation: int, externals: tuple[Monitor, ...]) -> None:
        if externals:
            waited = 0.0
            while not self._ready_check():
                if generation != self._generation or waited >= self.BACKEND_WAIT_SECONDS:
                    return
                self._sleep(0.5)
                waited += 0.5
        with self._lock:
            if generation != self._generation:
                return
            if externals:
                self._projector.show_on(externals[0])
            else:
                self._projector.close()

    def reopen_projector(self) -> bool:
        """Rouvre la fenêtre projecteur (menu du tray) si un écran externe existe."""
        externals = self._last_externals
        if not externals:
            return False
        with self._lock:
            return self._projector.show_on(externals[0])

    def refresh_report(self) -> None:
        """Ré-émet l'état courant (le backend le garde en mémoire seulement)."""
        externals = self._last_externals
        self._spawn(
            self._reporter, self._state_url, len(externals),
            externals[0].resolution if externals else None,
            name="bobine-display-report-refresh",
        )

    def shutdown(self) -> None:
        self._generation += 1
        self._projector.close()
