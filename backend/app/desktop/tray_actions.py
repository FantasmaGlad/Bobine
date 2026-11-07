"""Actions rapides du menu de la barre système : état, pause, reprise et arrêt de la diffusion.

Elles passent par la façade REST de l'interface (`POST /api/playback|radio/{cible}/{action}`) : le menu ne fait que ce
que font l'écran de pilotage et la commande `bobine` (`bobine playback cable pause`), avec les mêmes verrous de canal.
Logique pure, sans pystray : le transport HTTP est injecté pour les tests (backend/tests/test_tray_actions.py) ;
`app.desktop.tray` fournit l'adresse du backend et monte le menu.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable

logger = logging.getLogger(__name__)

# (type de sortie, cible, libellé du menu) : vidéo par canal, radio par sortie.
OUTPUTS = (
    ("playback", "cable", "Câblé"),
    ("playback", "network", "Réseau"),
    ("radio", "cable", "Radio câblée"),
    ("radio", "network", "Radio réseau"),
)
STATE_LABELS = {
    "playing": "lecture", "paused": "en pause", "waiting": "en attente", "playlist_waiting": "en attente", "idle": "arrêtée",
    "stopped": "arrêtée",
}
STATE_TTL_SECONDS = 1.5
HTTP_TIMEOUT_SECONDS = 3.0

Transport = Callable[[str, str, float], dict | None]


def _http(method: str, url: str, timeout: float = HTTP_TIMEOUT_SECONDS) -> dict | None:
    request = urllib.request.Request(url, method=method, data=b"{}" if method == "POST" else None,
                                     headers={"Accept": "application/json", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def _state_path(kind: str, target: str) -> str:
    return f"/api/playback/state?channel={target}" if kind == "playback" else f"/api/radio/state?channel=radio_{target}"


def _action_path(kind: str, target: str, action: str) -> str:
    return f"/api/{kind}/{target}/{action}"


class Controls:
    """État mis en cache quelques instants (le menu se redessine plusieurs fois à l'ouverture) et actions rapides."""

    def __init__(self, admin_url: Callable[[], str], transport: Transport = _http, clock: Callable[[], float] = time.monotonic) -> None:
        self._admin_url, self._transport, self._clock = admin_url, transport, clock
        self._lock = threading.Lock()
        self._cache: tuple[float, dict[tuple[str, str], str | None]] | None = None

    def states(self) -> dict[tuple[str, str], str | None]:
        """État de chaque sortie ; `None` quand le backend ne répond pas."""
        with self._lock:
            if self._cache and self._clock() - self._cache[0] < STATE_TTL_SECONDS:
                return self._cache[1]
        result: dict[tuple[str, str], str | None] = {}
        for kind, target, _ in OUTPUTS:
            try:
                payload = self._transport("GET", self._admin_url() + _state_path(kind, target), HTTP_TIMEOUT_SECONDS)
                state = (payload or {}).get("state")
                result[(kind, target)] = state if isinstance(state, str) else "idle"
            except (urllib.error.URLError, OSError, ValueError):
                result[(kind, target)] = None
        with self._lock:
            self._cache = (self._clock(), result)
        return result

    def invalidate(self) -> None:
        with self._lock:
            self._cache = None

    def label(self, kind: str, target: str, name: str) -> str:
        """« Câblé : lecture — Pause », « Réseau : en pause — Reprendre », « Radio câblée : en attente »."""
        state = self.states().get((kind, target))
        if state is None:
            return f"{name} : hors ligne"
        text = f"{name} : {STATE_LABELS.get(state, state)}"
        action = self.next_action(state)
        return f"{text} — {'Pause' if action == 'pause' else 'Reprendre'}" if action else text

    @staticmethod
    def next_action(state: str | None) -> str | None:
        """`pause` pendant une lecture, `play` pendant une pause, rien sinon (rien à mettre en pause ni à reprendre)."""
        return {"playing": "pause", "paused": "play"}.get(state or "")

    def toggle(self, kind: str, target: str) -> bool:
        """Pause une sortie qui joue, reprend celle qui est en pause ; faux si rien n'a été envoyé ou si l'envoi a échoué."""
        self.invalidate()
        action = self.next_action(self.states().get((kind, target)))
        if action is None:
            return False
        ok = self._send(kind, target, action)
        self.invalidate()
        return ok

    def stop_all(self) -> int:
        """Arrête les quatre sorties ; renvoie le nombre d'arrêts acceptés (un échec n'empêche pas les autres)."""
        accepted = sum(self._send(kind, target, "stop") for kind, target, _ in OUTPUTS)
        self.invalidate()
        return accepted

    def _send(self, kind: str, target: str, action: str) -> bool:
        try:
            self._transport("POST", self._admin_url() + _action_path(kind, target, action), HTTP_TIMEOUT_SECONDS)
            return True
        except urllib.error.HTTPError as exc:  # canal verrouillé (409), inconnu (404)...
            logger.info("Action rapide %s %s %s refusée : %s", kind, target, action, exc.code)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            logger.info("Action rapide %s %s %s impossible : %s", kind, target, action, exc)
        return False


# Une issue de mise à jour plus ancienne n'est plus une nouvelle : la barre système n'a pas de mémoire entre deux lancements,
# sans ce délai chaque redémarrage re-notifierait la dernière mise à jour terminée.
UPDATE_NOTIFICATION_MAX_AGE_SECONDS = 600


def should_notify_update_outcome(status: dict, last_notified_started_at, now: float | None = None) -> bool:
    """Vrai pour une issue (terminée ou échouée) récente, jamais notifiée et non acquittée dans l'interface."""
    started_at = status.get("started_at")
    if status.get("step") not in ("done", "failed") or started_at is None:
        return False
    if started_at == last_notified_started_at or status.get("acknowledged_started_at") == started_at:
        return False
    finished_at = status.get("updated_at") or started_at
    return (time.time() if now is None else now) - finished_at <= UPDATE_NOTIFICATION_MAX_AGE_SECONDS
