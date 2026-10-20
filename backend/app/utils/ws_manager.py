import asyncio
import logging
import time

from fastapi import WebSocket

from app.radio_manager import LEGACY_RADIO_CHANNEL, normalize_radio_channel

logger = logging.getLogger(__name__)

# Keepalive : un ping toutes les 30s, un client sans pong dans les 20s qui
# suivent est considéré mort.
# Relâché depuis 20s/10s : un kiosk réel sur une liaison réseau
# lente/chargée (thread JS occupé à bufferiser un gros fichier vidéo) rate
# systématiquement la fenêtre de pong d'origine et se fait fermer par le
# serveur ~toutes les 30s en boucle, sans jamais laisser assez de temps
# ininterrompu à la vidéo/l'intro pour réellement démarrer.
PING_INTERVAL_SECONDS = 30.0
# porté de 20s à 60s — une
# WebView Android en arrière-plan (MainActivity non visible pendant que
# l'admin est ouvert dans Chrome) voit ses minuteurs JS fortement throttlés
# par le système (jusqu'à 1/minute après 5 min en arrière-plan), et ratait
# systématiquement l'ancienne fenêtre de pong, provoquant une fermeture puis
# reconnexion en boucle (constaté dans technical.log : "Client WebSocket
# sans pong dans le délai" toutes les ~4 minutes). Le coût d'un délai de
# détection plus long pour un VRAI client mort est acceptable ici (pas un
# service à forte volumétrie de connexions).
PONG_TIMEOUT_SECONDS = 60.0
# Borne le temps qu'un seul client lent/bloqué peut faire perdre à
# `broadcast()` — au-delà, ce client est considéré injoignable et fermé
# proprement (cf. `broadcast()`) plutôt que de retarder tous les autres.
# Porté de 1.0s à 3.0s après un test en conditions réelles sur Wi-Fi (pas
# seulement en local) : 1s classifiait à tort des envois simplement lents
# (latence Wi-Fi réelle, pas une connexion morte) comme injoignables,
# fermant des clients qui auraient très bien fini par recevoir le message.
BROADCAST_SEND_TIMEOUT_SECONDS = 3.0


# Évènements propres à UN canal de diffusion (champ `channel`) : seuls les
# clients abonnés à ce canal les reçoivent. Avant, chaque
# tick de position — état complet — partait vers TOUTES les connexions de TOUS
# les canaux et le tri se faisait côté client : CPU et réseau consommés pour
# rien (le coût croît avec le nombre d'écrans). Les autres évènements
# (`display_output`, `settings_change`, `force_reload`, `ping`…) concernent tout
# le monde et ne sont jamais filtrés.
CHANNEL_SCOPED_EVENTS = frozenset({"state_change", "cinema_state", "cinema_command"})


class ConnectionManager:
    """Diffuse les changements d'état de lecture à tous les clients connectés
    (écran kiosk + télécommandes PC/mobile).

    Process unique : toutes les connexions WebSocket vivent dans le même
    processus, `broadcast()` écrit donc directement sur les sockets locales,
    sans canal de diffusion externe à relayer.

    Gestion du rôle kiosk :
    Seul le kiosk "primaire" (premier arrivé, ou dont le `client_id` est déjà
    reconnu) envoie report_position. Les suivants sont en mode miroir
    (reçoivent les états, ne rapportent pas). Si le primaire se déconnecte,
    le suivant est promu automatiquement.
    """

    def __init__(self):
        self.active_connections: dict[WebSocket, asyncio.Task] = {}
        self._last_pong: dict[WebSocket, float] = {}
        # Listes ordonnées des kiosks connectés, PAR CANAL de diffusion : chaque canal a son
        # propre kiosk primaire (premier arrivé), source de la position de SA
        # lecture. Un kiosk câblé et un kiosk réseau ne se disputent jamais
        # le rôle.
        self._kiosk_connections: dict[str, list[WebSocket]] = {"cable": [], "network": [], "radio_cable": [], "radio_network": []}
        # Canal déclaré par chaque kiosk à son identify (pour le retrait).
        self._kiosk_channel: dict[WebSocket, str] = {}
        # Identifiant stable côté client (persistant across reconnects) et
        # dernier statut primaire/miroir connu — `is_primary_kiosk` lit ce
        # cache local pour rester synchrone et rapide (pas de calcul à
        # chaque report_position, qui peut arriver plusieurs fois par
        # seconde).
        self._kiosk_client_id: dict[WebSocket, str] = {}
        self._kiosk_primary_status: dict[WebSocket, bool] = {}
        # `client_id` actuellement reconnu primaire, par canal : une reconnexion (même client_id,
        # nouvelle WebSocket) reprend immédiatement son rôle primaire même si
        # son ancienne connexion (morte mais pas encore expirée côté
        # ping/pong) est toujours dans `_kiosk_connections`. Process unique : plus besoin d'un bail à durée de vie (Redis TTL) —
        # la libération est déclenchée de façon fiable par la déconnexion
        # réelle de CE processus (cf. _unregister_kiosk), donc un simple
        # mapping sans expiration suffit.
        self._primary_client_id: dict[str, str] = {}
        # Abonnements de canal déclarés par les clients (`subscribe` /
        # `identify`). Une connexion SANS entrée reçoit tout (anciens bundles
        # frontend en cache : comportement historique, aucune régression).
        self._subscriptions: dict[WebSocket, frozenset[str]] = {}
        # Page déclarée par chaque kiosk à son identify (« kiosk », « radio »...) et « spectateurs » : pages qui
        # suivent un canal sans en être l'écran (cinéma, grille, tableaux de bord). Purement informatif (carte des
        # périphériques) : aucun effet sur le rôle primaire/miroir ni sur la diffusion des évènements.
        self._kiosk_page: dict[WebSocket, str] = {}
        self._viewers: dict[WebSocket, dict[str, str]] = {}
        # boucle
        # asyncio principale, enregistrée une fois au démarrage
        # (`main.py::lifespan`) — permet à du code exécuté HORS boucle (un
        # endpoint FastAPI `def` synchrone tournant dans le threadpool, un
        # exécuteur d'import ffmpeg/io) de programmer un broadcast sans
        # jamais appeler une coroutine directement depuis le mauvais thread.
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Enregistre la boucle principale — voir `broadcast_threadsafe`."""
        self._loop = loop

    def broadcast_threadsafe(self, message: dict) -> None:
        """Version thread-safe de `broadcast()` (cf. `bind_loop`) : pour du
        code qui tourne dans un thread qui n'est PAS celui de la boucle
        asyncio (endpoints synchrones `def`, exécuteurs `ffmpeg_executor`/
        `io_executor`). Ne lève jamais — même philosophie que `broadcast()`
        lui-même, un échec de diffusion ne doit jamais faire échouer
        l'opération qui l'accompagne."""
        if self._loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)
        except Exception:
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
        # Gestion du rôle kiosk : si ce kiosk était le primaire, promouvoir le suivant.
        asyncio.create_task(self._unregister_kiosk(websocket))
        logger.info(f"Client WebSocket déconnecté ({len(self.active_connections)} au total)")

    def subscribe(self, websocket: WebSocket, channels) -> None:
        """Déclare les canaux dont ce client veut les évènements propres à un
        canal. Liste vide = aucun (client qui n'écoute que les évènements
        globaux, p. ex. thème/langue)."""
        # L'alias historique "radio" (poste radio unique d'avant les deux sorties)
        # est ramené à la sortie réseau : un client en cache qui s'abonne encore
        # à "radio" reçoit les évènements de la sortie réseau.
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

    # ------------------------------------------------------------------
    # Gestion du rôle primaire / miroir des kiosks
    # ------------------------------------------------------------------

    def _claim_primary(self, channel: str, client_id: str) -> bool:
        """Tente d'acquérir/reconfirmer le rôle primaire de `channel` pour
        `client_id`. Purement local (process unique) : aucune I/O, jamais
        d'échec possible — contrairement à l'ancien bail Redis, il n'y a plus
        de scénario "indisponible" à gérer en repli."""
        current = self._primary_client_id.get(channel)
        if current is None or current == client_id:
            self._primary_client_id[channel] = client_id
            return True
        return False

    def _release_primary(self, channel: str, client_id: str) -> None:
        """Libère le rôle primaire de `channel` s'il appartient encore à
        `client_id` — permet une reprise immédiate par un miroir au lieu
        d'attendre une expiration quelconque."""
        if self._primary_client_id.get(channel) == client_id:
            del self._primary_client_id[channel]

    async def register_kiosk(self, websocket: WebSocket, channel: str = "cable", client_id: str = "") -> bool:
        """Enregistre un kiosk sur SON canal et (ré)évalue son statut
        primaire/miroir. Appelé à l'identify initial ET (historiquement)
        périodiquement en renouvellement — retourne True si ce kiosk est/
        devient le primaire du canal. Reste une coroutine `async def` par
        cohérence avec ses appelants (aucune opération asynchrone réelle à
        l'intérieur depuis la suppression du bail Redis)."""
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
        """Écrans et télécommandes connectés : canal, page, rôle (primaire, miroir, spectateur) et adresse du client,
        regroupés quand ils ne diffèrent pas (`count`)."""
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

    def kiosk_count(self, channel: str) -> int:
        """Nombre d'écrans de diffusion (kiosques identifiés) sur ce canal."""
        if channel == LEGACY_RADIO_CHANNEL:
            channel = normalize_radio_channel(channel)
        return len(self._kiosk_connections.get(channel, []))

    def is_primary_kiosk(self, websocket: WebSocket) -> bool:
        """Retourne True si ce websocket est le kiosk primaire de son canal
        (dernier statut connu, mis à jour à chaque identify)."""
        return self._kiosk_primary_status.get(websocket, False)

    def kiosk_channel(self, websocket: WebSocket) -> str | None:
        """Canal déclaré par ce kiosk à son identify (None si pas un kiosk)."""
        return self._kiosk_channel.get(websocket)

    async def _unregister_kiosk(self, websocket: WebSocket) -> None:
        """Retire un kiosk de la liste de son canal et libère son rôle
        primaire (le cas échéant) pour une reprise immédiate. Si un autre
        kiosk local est présent sur le canal, on le pousse à retenter sa
        chance tout de suite plutôt que d'attendre son prochain
        renouvellement périodique."""
        channel = self._kiosk_channel.pop(websocket, None)
        was_primary = self._kiosk_primary_status.pop(websocket, False)
        client_id = self._kiosk_client_id.pop(websocket, None)
        if channel is None:
            return
        kiosks = self._kiosk_connections[channel]
        if websocket in kiosks:
            kiosks.remove(websocket)
        # Ne libère le rôle que si AUCUNE autre connexion locale ne porte
        # encore ce même (canal, client_id) : sinon une déconnexion tardive
        # de l'ANCIENNE socket d'un appareil (ping/pong met jusqu'à 50s à la
        # détecter morte) supprimerait le rôle déjà légitimement repris par
        # SA PROPRE reconnexion plus rapide — coupant à tort le vrai
        # primaire pendant quelques secondes, exactement le genre de blip
        # que ce correctif cherche à éliminer.
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
                # Ce kiosk s'est peut-être lui aussi déconnecté entre-temps.
                pass

    async def broadcast(self, message: dict):
        """
        Envoie à tous les clients WebSocket locaux, EN PARALLÈLE. Avant ce lot, l'envoi se
        faisait client par client, en série : un seul client dont le tampon
        TCP était plein (WebView Android en arrière-plan, Wi-Fi qui rame)
        retardait la diffusion pour TOUS les autres, y compris `position_tick`
        émis toutes les 250 ms — cause directe des commandes admin qui
        semblaient ne pas atteindre la sortie câblée ou arrivaient en retard.

        Ne DOIT jamais lever : un accroc ici ne doit pas faire remonter
        d'exception jusqu'à la commande appelante (ex. `manager.stop()`),
        sinon l'état interne change bien mais aucun client ne le sait jamais
        — exactement le bug qui faisait croire que stop/pause/lancement de
        programmation ne faisaient rien.
        """
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
            # BUG RÉEL trouvé en déployant sur la tablette pilote (pas en
            # relecture de code) : `self.disconnect(connection)` seul retire
            # la connexion de `active_connections` — il ne l'a JAMAIS
            # fermée. Le client, lui, ne reçoit ni frame de fermeture ni
            # erreur : son objet WebSocket reste `OPEN` indéfiniment de son
            # propre point de vue, alors que le serveur a cessé de lui
            # diffuser quoi que ce soit. Résultat observé : `position_tick`
            # s'arrête net, sans reconnexion, jusqu'au keepalive serveur
            # (jusqu'à 90s) — exactement le rapport utilisateur "dashboard
            # réseau qui freeze". `websocket.close()` AVANT `disconnect()`
            # (même ordre que le timeout de `_ping_loop` ci-dessous, déjà
            # correct) envoie la frame de fermeture au client, qui détecte
            # `onclose` immédiatement et se reconnecte proprement via son
            # propre backoff — au lieu de rester figé en silence.
            try:
                await connection.close()
            except Exception:
                pass
            self.disconnect(connection)

    async def broadcast_force_reload(self):
        """Demande à tous les clients navigateur connectés (PC/mobile/coach)
        de recharger leur page. Le kiosk, lui, est relancé
        directement via `systemctl restart` côté serveur ; recevoir aussi cet
        évènement ne lui pose pas de problème (rechargement idempotent)."""
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
