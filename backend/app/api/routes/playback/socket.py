"""WebSocket des écrans et des tableaux de bord : identification, synchronisation, commandes."""

import logging
import time

from fastapi import Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.contract import CHANNELS, DEFAULT_CHANNEL
from app.playback.manager import get_playback_manager
from app.radio_manager import (
    get_all_radio_managers,
    is_radio_channel,
    normalize_radio_channel,
)
from app.utils.boot_state import current_boot_id
from app.utils.ws_manager import manager as ws_manager

from .commands import execute_command
from .core import CommandRejected, _resolve_channel, router

logger = logging.getLogger(__name__)


@router.websocket("/ws/playback")
async def playback_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    await ws_manager.connect(websocket)
    is_kiosk = False
    kiosk_channel = DEFAULT_CHANNEL
    kiosk_client_id = ""
    try:
        # un écran réseau/radio ouvert depuis un moment ne fait que
        # RECONNECTER son WebSocket après un restart backend (reboot machine,
        # watchdog, crash...) — sans ce message, il resynchronise son ÉTAT
        # mais continue de tourner sur son ANCIEN bundle JS/HTML en mémoire.
        # `current_boot_id()` change à chaque lancement du service (cf.
        # boot_state.py) ; le client compare à la valeur vue à SA connexion
        # initiale et se recharge complètement (comme le bouton
        # « Synchronisation des écrans ») si elle a changé depuis.
        await websocket.send_json({"event": "boot_id", "boot_id": current_boot_id()})
        # Envoi immédiat de l'état courant DES DEUX CANAUX au nouveau client
        # (kiosk ou télécommande) : chaque message porte son champ channel,
        # le client ne garde que celui de son canal. Le champ is_primary
        # n'est pertinent que pour les kiosks ; il sera renseigné après
        # réception du message identify.
        for channel in CHANNELS:
            await websocket.send_json({
                "event": "state_change",
                "cause": "sync",
                "channel": channel,
                "data": get_playback_manager(channel).snapshot(),
            })
        # Sorties radio, hors CHANNELS (cable/network) : envoyées à part, même
        # mécanisme, un état par moteur.
        for radio_channel, radio_manager in get_all_radio_managers().items():
            await websocket.send_json({
                "event": "state_change",
                "cause": "sync",
                "channel": radio_channel,
                "data": radio_manager.snapshot(),
            })
        while True:
            message = await websocket.receive_json()
            # Identification du rôle du client.
            # Le kiosk envoie {"command": "identify", "params": {"role":
            # "kiosk", "channel": "cable"|"network"|"radio_cable"|"radio_network", "client_id":
            # "..."}} dès l'ouverture de la connexion (et de nouveau si
            # promu primaire, cf. évènement "promoted_primary"). On enregistre
            # son rôle SUR SON CANAL et on lui retourne son statut
            # primaire/miroir via un message dédié à chaque appel.
            if message.get("command") == "time_sync":
                # Mesure d'horloge façon NTP : répond
                # DIRECTEMENT à ce client avec l'heure serveur ; il en déduit
                # son décalage (milieu de l'aller-retour) pour calculer la
                # position cible de l'horloge de lecture.
                await websocket.send_json({
                    "event": "time_sync",
                    "t0": (message.get("params") or {}).get("t0"),
                    "server_ms": time.time() * 1000.0,
                })
                continue
            if message.get("command") == "subscribe":
                # Abonnement de canal : {"command": "subscribe",
                # "params": {"channels": ["cable", ...]}} — liste vide autorisée.
                requested = (message.get("params") or {}).get("channels")
                if isinstance(requested, list):
                    ws_manager.subscribe(websocket, [c for c in requested if isinstance(c, str)])
                continue
            if message.get("command") == "identify":
                params = message.get("params") or {}
                role = params.get("role")
                if role == "viewer":
                    # Page qui suit un canal sans être son écran (cinéma, grille, tableau de bord) : simple
                    # déclaration pour la carte des périphériques, sans rôle primaire ni effet sur la lecture.
                    ws_manager.register_viewer(websocket, str(_resolve_channel(params.get("channel"))), str(params.get("page") or "viewer"))
                    continue
                if role == "kiosk":
                    if not is_kiosk:
                        is_kiosk = True
                        requested_channel = params.get("channel")
                        # Le poste /radio est le lecteur primaire d'UNE sortie
                        # radio, hors CHANNELS (cable/network) : _resolve_channel
                        # le ferait retomber sur "cable" à tort. L'alias
                        # historique "radio" désigne la sortie réseau.
                        kiosk_channel = (
                            normalize_radio_channel(requested_channel)
                            if is_radio_channel(requested_channel)
                            else _resolve_channel(requested_channel)
                        )
                        # Identifiant stable persistant côté client (localStorage) —
                        # repli sur l'identité de CETTE connexion si absent (vieux
                        # bundle frontend en cache), auquel cas le bail se comporte
                        # comme avant (pas de reprise cross-worker, sans régression).
                        kiosk_client_id = params.get("client_id") or f"conn-{id(websocket)}"
                    is_primary = await ws_manager.register_kiosk(websocket, kiosk_channel, kiosk_client_id)
                    ws_manager.set_kiosk_page(websocket, params.get("page") if isinstance(params.get("page"), str) else None)
                    await websocket.send_json({
                        "event": "kiosk_role",
                        "is_primary": is_primary,
                    })
                continue
            try:
                await execute_command(message, db, websocket, is_kiosk=is_kiosk, default_channel=kiosk_channel)
            except CommandRejected as rejected:
                # Refus renvoyé au seul émetteur (jamais diffusé) : l'admin qui a cliqué peut l'afficher.
                await websocket.send_json({
                    "event": "command_rejected", "command": message.get("command"),
                    "reason": rejected.reason, "channel": rejected.channel,
                })
            except WebSocketDisconnect:
                raise
            except Exception as e:
                # Une commande en échec ne coupe pas la connexion de l'écran ou du tableau de bord qui l'a envoyée.
                logger.error(f"Commande WebSocket {message.get('command')} en échec : {e}", exc_info=True)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Erreur sur la connexion WebSocket playback : {e}", exc_info=True)
        ws_manager.disconnect(websocket)
