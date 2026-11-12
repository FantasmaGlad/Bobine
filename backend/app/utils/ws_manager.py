import asyncio
import logging
import time

from fastapi import WebSocket

from app.radio_manager import LEGACY_RADIO_CHANNEL, normalize_radio_channel

logger = logging.getLogger(__name__)

PING_INTERVAL_SECONDS = 30.0
PONG_TIMEOUT_SECONDS = 60.0
BROADCAST_SEND_TIMEOUT_SECONDS = 3.0


CHANNEL_SCOPED_EVENTS = frozenset({"state_change", "cinema_state", "cinema_command", "radio_levels"})


class ConnectionManager:
    """Diffuse les changements d'état de lecture à tous les clients connectés (écran kiosk + télécommandes PC/mobile)."""

    def __init__(self):
        self.active_connections: dict[WebSocket, asyncio.Task] = {}
        self._last_pong: dict[WebSocket, float] = {}
        self._kiosk_connections: dict[str, list[WebSocket]] = {"cable": [], "network": [], "radio_cable": [], "radio_network": []}
        self._kiosk_channel: dict[WebSocket, str] = {}
        self._kiosk_client_id: dict[WebSocket, str] = {}
        self._kiosk_primary_status: dict[WebSocket, bool] = {}
        self._primary_client_id: dict[str, str] = {}
        self._subscriptions: dict[WebSocket, frozenset[str]] = {}
        self._kiosk_page: dict[WebSocket, str] = {}
        self._viewers: dict[WebSocket, dict[str, str]] = {}
        self._route_reports: dict[WebSocket, dict[str, str]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Enregistre la boucle principale — voir `broadcast_threadsafe`."""
        self._loop = loop

    def broadcast_threadsafe(self, message: dict) -> None:
        """Version thread-safe de `broadcast()`."""
        loop = self._loop
        if loop is None or loop.is_closed() or not loop.is_running():
            return
        def send_on_loop() -> None:
            loop.create_task(self.broadcast(message))

        try:
            loop.call_soon_threadsafe(send_on_loop)
        except RuntimeError:
            logger.warning("broadcast_threadsafe : échec de programmation sur la boucle", exc_info=True)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._last_pong[websocket] = time.monotonic()
        self.active_connections[websocket] = asyncio.create_task(self._ping_loop(websocket))
        logger.info(f"Client WebSocket connecté ({len(self.active_connections)} au total)")

    def disconnect(self, websocket: WebSocket):
        task = self.active_connections.pop(websocket, None)
        if task:
            task.cancel()
        self._last_pong.pop(websocket, None)
        self._subscriptions.pop(websocket, None)
        self._viewers.pop(websocket, None)
        self._kiosk_page.pop(websocket, None)
        self._route_reports.pop(websocket, None)
        asyncio.create_task(self._unregister_kiosk(websocket))
        logger.info(f"Client WebSocket déconnecté ({len(self.active_connections)} au total)")

    def subscribe(self, websocket: WebSocket, channels) -> None:
        """Déclare les canaux dont ce client veut les évènements propres à un canal."""
        self._subscriptions[websocket] = frozenset(
            normalize_radio_channel(c) if c == LEGACY_RADIO_CHANNEL else str(c) for c in channels
        )

    def _wants(self, websocket: WebSocket, message: dict) -> bool:
        subscribed = self._subscriptions.get(websocket)
        if subscribed is None or message.get("event") not in CHANNEL_SCOPED_EVENTS:
            return True
        channel = message.get("channel")
        return channel is None or channel in subscribed

    def note_pong(self, websocket: WebSocket):
        """Appelé quand un client répond {"command": "pong"} à notre ping."""
        self._last_pong[websocket] = time.monotonic()


    def _claim_primary(self, channel: str, client_id: str) -> bool:
        current = self._primary_client_id.get(channel)
        if current is None or current == client_id:
            self._primary_client_id[channel] = client_id
            return True
        return False

    def _release_primary(self, channel: str, client_id: str) -> None:
        if self._primary_client_id.get(channel) == client_id:
            del self._primary_client_id[channel]

    async def register_kiosk(self, websocket: WebSocket, channel: str = "cable", client_id: str = "") -> bool:
        """Enregistre un kiosk sur SON canal et (ré)évalue son statut primaire/miroir."""
        if channel == LEGACY_RADIO_CHANNEL:
            channel = normalize_radio_channel(channel)
        if channel not in self._kiosk_connections:
            channel = "cable"
        kiosks = self._kiosk_connections[channel]
        if websocket not in kiosks:
            kiosks.append(websocket)
        self._kiosk_channel[websocket] = channel
        self._kiosk_client_id[websocket] = client_id
        self.subscribe(websocket, (channel,))
        is_primary = self._claim_primary(channel, client_id)
        self._kiosk_primary_status[websocket] = is_primary
        logger.info(
            f"Kiosk enregistré sur le canal '{channel}' — rôle : {'primaire' if is_primary else 'miroir'} "
            f"({len(kiosks)} kiosk(s) sur ce canal)"
        )
        return is_primary

    def register_viewer(self, websocket: WebSocket, channel: str, page: str) -> None:
        """Déclare une page qui suit un canal sans être son écran (cinéma, grille, tableau de bord)."""
        if channel not in ("cable", "network"):
            channel = "cable"
        self._viewers[websocket] = {"channel": channel, "page": page[:24]}

    def set_kiosk_page(self, websocket: WebSocket, page: str | None) -> None:
        if page:
            self._kiosk_page[websocket] = page[:24]

    def client_snapshot(self) -> list[dict[str, object]]:
        """Écrans et télécommandes connectés : canal, page, rôle (primaire, miroir, spectateur) et adresse du client, regroupés quand ils ne diffèrent pas (`count`)."""
        entries: list[tuple[str, str, str, str]] = []

        def ip_of(ws: WebSocket) -> str:
            client = getattr(ws, "client", None)
            return str(client.host) if client else ""

        for channel, kiosks in self._kiosk_connections.items():
            for ws in kiosks:
                page = self._kiosk_page.get(ws) or ("radio" if channel.startswith("radio") else "kiosk")
                role = "primary" if self._kiosk_primary_status.get(ws) else "mirror"
                entries.append((channel, page, role, ip_of(ws)))
        for ws, info in self._viewers.items():
            entries.append((info["channel"], info["page"], "viewer", ip_of(ws)))
        grouped: dict[tuple[str, str, str, str], int] = {}
        for entry in entries:
            grouped[entry] = grouped.get(entry, 0) + 1
        return [
            {"channel": c, "page": p, "role": r, "ip": ip, "count": n}
            for (c, p, r, ip), n in sorted(grouped.items())
        ]

    def set_route_report(self, websocket: WebSocket, report: dict[str, str]) -> bool:
        """Mémorise le résultat de routage d'un lecteur /radio identifié ; faux (ignoré) pour toute autre connexion."""
        if websocket not in self._kiosk_channel:
            return False
        self._route_reports[websocket] = report
        return True

    def route_players(self, channel: str) -> list[dict[str, object]]:
        """Lecteurs /radio connectés pour une sortie radio, avec leur adresse, leur rôle et leur dernier rapport de routage."""
        players: list[dict[str, object]] = []
        for ws in self._kiosk_connections.get(channel, []):
            client = getattr(ws, "client", None)
            players.append({
                "ip": str(client.host) if client else "",
                "primary": bool(self._kiosk_primary_status.get(ws)),
                "page": self._kiosk_page.get(ws) or "radio",
                "report": self._route_reports.get(ws),
            })
        return players

    def kiosk_count(self, channel: str) -> int:
        """Nombre d'écrans de diffusion (kiosques identifiés) sur ce canal."""
        if channel == LEGACY_RADIO_CHANNEL:
            channel = normalize_radio_channel(channel)
        return len(self._kiosk_connections.get(channel, []))

    def is_primary_kiosk(self, websocket: WebSocket) -> bool:
        """Retourne True si ce websocket est le kiosk primaire de son canal (dernier statut connu, mis à jour à chaque identify)."""
        return self._kiosk_primary_status.get(websocket, False)

    def kiosk_channel(self, websocket: WebSocket) -> str | None:
        """Canal déclaré par ce kiosk à son identify (None si pas un kiosk)."""
        return self._kiosk_channel.get(websocket)

    async def _unregister_kiosk(self, websocket: WebSocket) -> None:
        channel = self._kiosk_channel.pop(websocket, None)
        was_primary = self._kiosk_primary_status.pop(websocket, False)
        client_id = self._kiosk_client_id.pop(websocket, None)
        if channel is None:
            return
        kiosks = self._kiosk_connections[channel]
        if websocket in kiosks:
            kiosks.remove(websocket)
        still_present = any(
            self._kiosk_channel.get(other) == channel and self._kiosk_client_id.get(other) == client_id
            for other in kiosks
        )
        if was_primary and client_id and not still_present:
            self._release_primary(channel, client_id)
        if kiosks:
            logger.info(f"Kiosk du canal '{channel}' déconnecté — invitation du suivant à retenter le rôle primaire")
            next_kiosk = kiosks[0]
            try:
                await next_kiosk.send_json({"event": "promoted_primary"})
            except Exception:
                pass

    async def broadcast(self, message: dict):
        """Envoie à tous les clients WebSocket locaux, EN PARALLÈLE."""
        connections = [c for c in self.active_connections.keys() if self._wants(c, message)]
        if not connections:
            return

        async def _send_one(connection: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(
                    connection.send_json(message), timeout=BROADCAST_SEND_TIMEOUT_SECONDS
                )
                return None
            except Exception:
                return connection

        results = await asyncio.gather(*(_send_one(c) for c in connections))
        for connection in results:
            if connection is None:
                continue
            try:
                await connection.close()
            except Exception:
                pass
            self.disconnect(connection)

    async def broadcast_force_reload(self):
        """Demande à tous les clients navigateur connectés (PC/mobile/coach) de recharger leur page."""
        await self.broadcast({"event": "force_reload"})

    async def _ping_loop(self, websocket: WebSocket):
        try:
            while True:
                await asyncio.sleep(PING_INTERVAL_SECONDS)
                sent_at = time.monotonic()
                try:
                    await websocket.send_json({"event": "ping"})
                except Exception:
                    self.disconnect(websocket)
                    return
                await asyncio.sleep(PONG_TIMEOUT_SECONDS)
                if self._last_pong.get(websocket, 0.0) < sent_at:
                    logger.info("Client WebSocket sans pong dans le délai — fermeture (connexion morte)")
                    try:
                        await websocket.close()
                    except Exception:
                        pass
                    self.disconnect(websocket)
                    return
        except asyncio.CancelledError:
            pass


manager = ConnectionManager()
