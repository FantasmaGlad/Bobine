from __future__ import annotations

from app.api.contract import AUDIO_TEST_CHANNELS, RADIO_CHANNELS, ROUTING_FALLBACKS

from .model import Spec
from .route import route

_AUDIO = "/api/devices/audio"
_BT = "/api/devices/bluetooth"
_WIFI = "/api/devices/wifi"

SPECS: tuple[Spec, ...] = (
    route("devices", "audio-details", "GET", f"{_AUDIO}/details", "détail d'une sortie audio", query=("id",), pos=("id",)),
    route("devices", "audio-default", "POST", f"{_AUDIO}/default", "choisir la sortie audio par défaut", body=("id",), pos=("id",)),
    route("devices", "audio-volume", "POST", f"{_AUDIO}/volume", "volume ou sourdine d'une sortie",
          body=("id", "volume:float", "muted:bool"), pos=("id",), require_one=True),
    route("devices", "audio-balance", "POST", f"{_AUDIO}/balance", "balance gauche-droite (-1 à 1)",
          body=("id", "balance:float"), pos=("id", "balance")),
    route("devices", "audio-test", "POST", f"{_AUDIO}/test", "son de test sur un canal", body=("id", "channel=" + "|".join(AUDIO_TEST_CHANNELS)), pos=("id", "channel")),
    route("devices", "audio-profile", "POST", f"{_AUDIO}/profile", "choisir un profil de carte son",
          body=("id", "index:int"), pos=("id", "index")),
    route("devices", "audio-meta", "PUT", f"{_AUDIO}/meta", "nom affiché ou masquage d'une sortie",
          body=("id", "alias", "hidden:bool"), pos=("id",), require_one=True),
    route("devices", "bt-permission", "POST", f"{_BT}/permission", "demander l'autorisation Bluetooth"),
    route("devices", "bt-power", "POST", f"{_BT}/power", "allumer ou éteindre le Bluetooth", body=("on:bool",), pos=("on",)),
    route("devices", "bt-scan", "POST", f"{_BT}/scan", "lancer ou arrêter la recherche", body=("on:bool",), pos=("on",)),
    route("devices", "bt-pair", "POST", f"{_BT}/pair", "appairer un appareil", body=("address",), pos=("address",)),
    route("devices", "bt-respond", "POST", f"{_BT}/pairing/respond", "accepter ou refuser un appairage",
          body=("address", "accept:bool"), pos=("address", "accept")),
    route("devices", "bt-connect", "POST", f"{_BT}/connect", "connecter un appareil", body=("address",), pos=("address",)),
    route("devices", "bt-disconnect", "POST", f"{_BT}/disconnect", "déconnecter un appareil", body=("address",), pos=("address",)),
    route("devices", "bt-forget", "POST", f"{_BT}/forget", "oublier un appareil", body=("address",), pos=("address",),
          confirm="Oublier l'appareil {address} ?"),
    route("devices", "wifi-scan", "POST", f"{_WIFI}/scan", "rechercher les réseaux Wi-Fi"),
    route("devices", "wifi-power", "POST", f"{_WIFI}/power", "allumer ou éteindre le Wi-Fi",
          body=("on:bool", "acknowledge_disconnect:bool"), pos=("on",)),
    route("devices", "wifi-connect", "POST", f"{_WIFI}/connect", "se connecter à un réseau (à confirmer ensuite)",
          body=("ssid", "password", "acknowledge_disconnect:bool"), pos=("ssid",)),
    route("devices", "wifi-confirm", "POST", f"{_WIFI}/confirm", "confirmer le nouveau réseau Wi-Fi"),
    route("devices", "wifi-forget", "POST", f"{_WIFI}/forget", "oublier un réseau",
          body=("ssid", "acknowledge_disconnect:bool"), pos=("ssid",), confirm="Oublier le réseau {ssid} ?"),
    route("devices", "routing", "GET", "/api/devices/routing", "sortie audio de chaque canal"),
    route("devices", "routing-set", "PUT", "/api/devices/routing", "diriger un canal vers une sortie audio",
          body=("channel=" + "|".join(RADIO_CHANNELS), "sink_id", "fallback=" + "|".join(ROUTING_FALLBACKS), "clear:bool"),
          pos=("channel",)),
    route("devices", "mixer", "GET", "/api/devices/mixer", "table de mixage par canal"),
    route("devices", "mixer-set", "PUT", "/api/devices/mixer/{channel}", "régler le mixage d'un canal (JSON)",
          body=("mix:json", "sound:json"), require_one=True),
    route("devices", "system-settings", "POST", "/api/devices/system-settings", "ouvrir un réglage du système sur la machine",
          body=("target",), pos=("target",)),
)
