"""Routage audio par sortie radio (phase 2) : à quelle sortie PHYSIQUE de la machine chaque sortie radio doit jouer.

Ce module est PUR (aucun accès au système) sauf `load_*`/`save_*`, qui lisent et écrivent `settings` :

* une route est un DESCRIPTEUR STABLE de la sortie choisie (clé, libellés, type), pas l'identifiant PipeWire du
  moment : un haut-parleur Bluetooth qui se reconnecte change de nœud mais garde sa clé (`bt:<MAC>`), et la route
  se rétablit seule (« mémorisation par périphérique ») ;
* la route est PUBLIÉE aux lecteurs dans l'état de la sortie radio (champ `route`), comme le réglage de son ;
  le lecteur l'applique lui-même quand son navigateur le permet (`lib/audioRoute.ts`) ;
* tout est borné sans erreur : une valeur aberrante est ramenée à une valeur valide, jamais d'exception.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any

from sqlalchemy.orm import Session

from app.models import Setting
from app.radio_manager import RADIO_CHANNELS

logger = logging.getLogger(__name__)

ROUTES_SETTING = "devices_audio_routes"
FALLBACKS = ("default", "mute")
DEFAULT_FALLBACK = "default"
AUDIO_KINDS = ("internal", "hdmi", "usb", "jack", "bluetooth", "virtual", "other")

_MAX_ID = 256
_MAX_LABEL = 120
_MAX_LABELS = 4

# `bluez_output.88_92_CC_9C_41_0E.1`, `bluez_output.….a2dp-sink`, `bluez_sink.….a2dp_sink` : la MAC ne change pas avec le profil.
_BT_SINK_RE = re.compile(r"^bluez_(?:output|sink)\.((?:[0-9A-Fa-f]{2}_){5}[0-9A-Fa-f]{2})(?:\.|$)")


def stable_sink_key(sink_id: str) -> str:
    """Clé qui survit à une reconnexion : `bt:AA:BB:…` pour le Bluetooth (indépendante du profil A2DP/HFP),
    `node:<nom PipeWire>` sinon (les cartes ALSA gardent leur nom tant que le matériel est le même)."""
    match = _BT_SINK_RE.match(sink_id or "")
    if match:
        return "bt:" + match.group(1).replace("_", ":").upper()
    return f"node:{sink_id}"


def normalize_label(text: str) -> str:
    """Casse, accents et ponctuation ignorés : « Haut‑parleurs (Realtek) » ≈ « haut parleurs realtek »."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    base = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", base.lower()).strip()


def describe_sink(sink: dict[str, Any]) -> dict[str, Any]:
    """Descripteur persistant d'une entrée de `audio_list()` (alias de Bobine compris pour l'affichage)."""
    sink_id = str(sink.get("id") or "")
    labels: list[str] = []
    for candidate in (sink.get("name"), sink.get("description")):
        text = str(candidate or "").strip()[:_MAX_LABEL]
        if text and normalize_label(text) not in {normalize_label(x) for x in labels}:
            labels.append(text)
    kind = sink.get("kind") if sink.get("kind") in AUDIO_KINDS else "other"
    display = str(sink.get("alias") or sink.get("name") or sink_id).strip()[:_MAX_LABEL]
    return {
        "sink_id": sink_id[:_MAX_ID],
        "key": stable_sink_key(sink_id)[:_MAX_ID],
        "label": display,
        "labels": labels[:_MAX_LABELS],
        "kind": kind,
    }


def _clean_route(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    sink_id = str(raw.get("sink_id") or "").strip()[:_MAX_ID]
    key = str(raw.get("key") or "").strip()[:_MAX_ID]
    if not sink_id or not key:
        return None
    labels_in = raw.get("labels")
    labels = [str(x).strip()[:_MAX_LABEL] for x in labels_in if isinstance(x, str) and x.strip()] if isinstance(labels_in, list) else []
    fallback = raw.get("fallback")
    return {
        "sink_id": sink_id,
        "key": key,
        "label": str(raw.get("label") or sink_id).strip()[:_MAX_LABEL],
        "labels": labels[:_MAX_LABELS],
        "kind": raw.get("kind") if raw.get("kind") in AUDIO_KINDS else "other",
        "fallback": fallback if fallback in FALLBACKS else DEFAULT_FALLBACK,
    }


def sanitize_routes(raw: Any) -> dict[str, dict[str, Any]]:
    """`{sortie radio: route}` valide ; entrées inconnues ou illisibles écartées."""
    if not isinstance(raw, dict):
        return {}
    routes: dict[str, dict[str, Any]] = {}
    for channel in RADIO_CHANNELS:
        route = _clean_route(raw.get(channel))
        if route is not None:
            routes[channel] = route
    return routes


def resolve_route(route: dict[str, Any] | None, sinks: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Où en est une route : `default` (aucune route), `routed` (sortie présente), `missing` (sortie débranchée, route
    conservée) ou `unknown` (liste des sorties indisponible sur cette plateforme)."""
    if route is None:
        return {"state": "default", "sink": None}
    if sinks is None:
        return {"state": "unknown", "sink": None}
    candidates = [s for s in sinks if s.get("available", True) and stable_sink_key(str(s.get("id"))) == route["key"]]
    if not candidates:
        return {"state": "missing", "sink": None}
    exact = next((s for s in candidates if s.get("id") == route["sink_id"]), candidates[0])
    return {"state": "routed", "sink": exact}


def player_route_state(route: dict[str, Any] | None, resolution: dict[str, Any]) -> dict[str, Any] | None:
    """Ce que le lecteur de la sortie radio reçoit (champ `route` de l'état) : de quoi retrouver la sortie dans les
    périphériques de SON navigateur (libellés du système, ceux de la sortie actuelle si elle est présente) et le repli.
    Pas d'identifiant de nœud ni d'adresse : seulement des noms de sortie audio."""
    if route is None:
        return None
    labels = list(route["labels"])
    sink = resolution.get("sink")
    if sink is not None:
        current = describe_sink(sink)["labels"]
        labels = current + [x for x in labels if normalize_label(x) not in {normalize_label(y) for y in current}]
    return {
        "key": route["key"],
        "label": route["label"],
        "match": labels[:_MAX_LABELS],
        "kind": route["kind"],
        "fallback": route["fallback"],
        "state": resolution["state"],
    }


# ---------------------------------------------------------------------------
# Persistance (`settings`)
# ---------------------------------------------------------------------------


def load_routes(db: Session) -> dict[str, dict[str, Any]]:
    row = db.query(Setting).filter(Setting.key == ROUTES_SETTING).first()
    if row is None or not row.value:
        return {}
    try:
        return sanitize_routes(json.loads(row.value))
    except (TypeError, ValueError):
        logger.warning("Routes audio illisibles : aucune route appliquée")
        return {}


def save_routes(db: Session, routes: dict[str, dict[str, Any]]) -> None:
    row = db.query(Setting).filter(Setting.key == ROUTES_SETTING).first()
    clean = sanitize_routes(routes)
    if not clean:
        if row is not None:
            db.delete(row)
            db.commit()
        return
    payload = json.dumps(clean, ensure_ascii=False)
    if row is None:
        db.add(Setting(key=ROUTES_SETTING, value=payload))
    else:
        row.value = payload
    db.commit()


def load_routes_into_managers(db: Session) -> None:
    """Au démarrage : publie les routes mémorisées dans l'état des deux sorties radio (état « inconnu » tant que le pilote
    n'a pas dit quelles sorties sont présentes ; `DevicesService.reconcile_routes` le précise ensuite)."""
    from app.radio_manager import get_all_radio_managers

    routes = load_routes(db)
    for channel, manager in get_all_radio_managers().items():
        route = routes.get(channel)
        manager.state["route"] = player_route_state(route, resolve_route(route, None))
