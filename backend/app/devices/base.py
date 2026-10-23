"""Interface commune des pilotes de périphériques (audio, Bluetooth, Wi-Fi).

Un pilote par plateforme (Linux : `linux.py`, Windows/macOS : sidecar Rust `sidecar.py`,
Android : pont Kotlin `android.py`) ; le routeur `routers/devices.py` ne connaît que cette
interface. Règles d'or :

* un pilote DÉCLARE ses capacités (`capabilities()`) — l'interface n'affiche que ce que
  l'OS permet, jamais un bouton qui échouera ;
* aucune erreur d'OS ne remonte en exception brute : un pilote lève `DeviceError` (code
  stable + message lisible) ou renvoie `unsupported(...)`, jamais une 500.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

# Évènement émis par un pilote quand son état change de lui-même (branchement, appairage...).
# Le service le relaie en WebSocket sous forme de simple signal (sans données) : les clients
# relisent ensuite l'état par REST, derrière le contrôle d'accès (PIN) du routeur.
ChangeCallback = Callable[[str], None]

SCOPES = ("audio", "bluetooth", "wifi")

# Capacités connues, toutes fausses par défaut : un pilote n'active que ce qu'il sait faire.
CAPABILITY_KEYS = (
    "audio_list",
    "audio_set_default",
    "audio_set_volume",
    "audio_details",
    "audio_balance",
    "audio_test_tone",
    "audio_profile",
    "audio_route_stream",
    "bluetooth_status",
    "bluetooth_power",
    "bluetooth_scan",
    "bluetooth_pair",
    "bluetooth_connect",
    "bluetooth_forget",
    "wifi_status",
    "wifi_power",
    "wifi_scan",
    "wifi_connect",
    "wifi_forget",
    "system_settings",
)


class DeviceError(Exception):
    """Erreur d'OS convertie en réponse structurée (jamais une 500)."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def unsupported(reason: str, **extra: Any) -> dict[str, Any]:
    """Réponse standard d'une fonction que la plateforme ne permet pas."""
    return {"supported": False, "reason": reason, **extra}


def no_capabilities(reason: str) -> dict[str, dict[str, Any]]:
    """Toutes les capacités à faux, avec la même raison (pilote nul)."""
    return {key: {"supported": False, "reason": reason} for key in CAPABILITY_KEYS}


class DeviceDriver(ABC):
    """Contrat d'un pilote. Toutes les méthodes sont asynchrones et ne bloquent pas la boucle."""

    #: identifiant du pilote ("linux", "sidecar", "android", "none")
    name: str = "none"

    def __init__(self) -> None:
        self._on_change: ChangeCallback | None = None

    def set_change_callback(self, callback: ChangeCallback | None) -> None:
        self._on_change = callback

    def _emit(self, scope: str) -> None:
        if self._on_change is not None:
            try:
                self._on_change(scope)
            except Exception:  # un abonné fautif ne doit jamais casser le pilote
                pass

    async def start(self) -> None:  # pragma: no cover - crochet optionnel
        """Démarre les ressources longues (agent d'appairage, sous-processus...)."""

    async def stop(self) -> None:  # pragma: no cover - crochet optionnel
        """Libère les ressources longues."""

    # --- capacités -------------------------------------------------------
    @abstractmethod
    async def capabilities(self) -> dict[str, dict[str, Any]]:
        """`{clé: {"supported": bool, "reason"?: str}}` pour chaque clé de CAPABILITY_KEYS."""

    # --- audio -----------------------------------------------------------
    @abstractmethod
    async def audio_list(self) -> dict[str, Any]:
        """`{"supported": True, "devices": [...], "default_id": str|None}` ou `unsupported()`.

        Chaque appareil : id, name, description, kind (internal|hdmi|usb|jack|bluetooth|virtual|other),
        is_default, volume (0..1|None), muted (bool|None), available (bool)."""

    async def audio_set_default(self, device_id: str) -> None:
        raise DeviceError("unsupported", "Changer la sortie audio par défaut n'est pas possible sur cette plateforme.", 501)

    async def audio_set_volume(self, device_id: str, volume: float | None, muted: bool | None) -> None:
        raise DeviceError("unsupported", "Régler le volume système n'est pas possible sur cette plateforme.", 501)

    async def audio_details(self, device_id: str) -> dict[str, Any]:
        """Analyse d'une sortie : état, canaux, fréquence, format, latence, carte, profil, codec Bluetooth, balance.
        `{"supported": False, "reason"}` quand la plateforme ne sait pas le dire."""
        return unsupported("L'analyse détaillée d'une sortie audio n'est pas disponible sur cette plateforme.")

    async def audio_set_balance(self, device_id: str, balance: float) -> None:
        """Balance gauche/droite, de -1 (tout à gauche) à +1 (tout à droite), niveau maître conservé."""
        raise DeviceError("unsupported", "La balance gauche/droite n'est pas réglable sur cette plateforme.", 501)

    async def audio_test_tone(self, device_id: str, channel: str) -> None:
        """Joue brièvement une tonalité de test (`left`, `right` ou `both`) sur cette sortie."""
        raise DeviceError("unsupported", "Le son de test n'est pas disponible sur cette plateforme.", 501)

    async def audio_set_profile(self, device_id: str, profile_index: int) -> None:
        raise DeviceError("unsupported", "Le changement de profil audio n'est pas possible sur cette plateforme.", 501)

    async def audio_route_stream(self, sink_id: str | None) -> dict[str, Any]:
        """Phase 2 (routage par sortie radio) : amène vers `sink_id` le flux audio du navigateur qui joue la radio
        sur CETTE machine, ou le rend à la sortie par défaut (`None`). Ne déplace un flux que s'il est identifiable
        sans ambiguïté. Renvoie `{"status": "moved"|"unchanged"|"released"|"no_stream"|"ambiguous"|"failed"}`."""
        raise DeviceError("unsupported", "Le déplacement du flux audio d'une application n'est pas possible sur cette plateforme.", 501)

    # --- Bluetooth -------------------------------------------------------
    @abstractmethod
    async def bluetooth_status(self) -> dict[str, Any]:
        """`{"supported": True, "powered": bool, "discovering": bool, "devices": [...],
        "pending_pairing": {...}|None}` ou `unsupported()`.

        Chaque appareil : address, name, paired, connected, trusted, rssi, kind, battery."""

    async def bluetooth_request_permission(self) -> None:
        """Demande l'autorisation système d'utiliser le Bluetooth (Android : « Appareils à proximité »)."""

    async def bluetooth_set_power(self, on: bool) -> None:
        raise DeviceError("unsupported", "Le Bluetooth ne peut pas être activé ici.", 501)

    async def bluetooth_scan(self, on: bool) -> None:
        raise DeviceError("unsupported", "La recherche Bluetooth n'est pas possible ici.", 501)

    async def bluetooth_pair(self, address: str) -> None:
        raise DeviceError("unsupported", "L'appairage Bluetooth doit se faire dans les réglages du système.", 501)

    async def bluetooth_respond_pairing(self, address: str, accept: bool) -> None:
        raise DeviceError("unsupported", "Aucun appairage en attente.", 501)

    async def bluetooth_connect(self, address: str) -> None:
        raise DeviceError("unsupported", "La connexion Bluetooth n'est pas possible ici.", 501)

    async def bluetooth_disconnect(self, address: str) -> None:
        raise DeviceError("unsupported", "La déconnexion Bluetooth n'est pas possible ici.", 501)

    async def bluetooth_forget(self, address: str) -> None:
        raise DeviceError("unsupported", "L'oubli d'un appareil Bluetooth n'est pas possible ici.", 501)

    # --- Wi-Fi -----------------------------------------------------------
    @abstractmethod
    async def wifi_status(self) -> dict[str, Any]:
        """`{"supported": True, "enabled": bool, "interface": str|None, "current": {...}|None,
        "networks": [...], "known": [...]}` ou `unsupported()`.

        current : ssid, signal (0..100), band, ip, security. networks : ssid, signal, security,
        band, known (bool), in_use (bool)."""

    async def wifi_set_power(self, on: bool) -> None:
        raise DeviceError("unsupported", "Le Wi-Fi ne peut pas être activé ici.", 501)

    async def wifi_scan(self) -> None:
        raise DeviceError("unsupported", "La recherche de réseaux Wi-Fi n'est pas possible ici.", 501)

    async def wifi_current_connection(self) -> str | None:
        """Nom de la connexion Wi-Fi active (pour le retour automatique), si connue."""
        return None

    async def wifi_connect(self, ssid: str, password: str | None) -> None:
        raise DeviceError("unsupported", "La connexion Wi-Fi doit se faire dans les réglages du système.", 501)

    async def wifi_activate(self, connection: str) -> None:
        """Réactive une connexion enregistrée (retour automatique)."""
        raise DeviceError("unsupported", "Réactivation impossible sur cette plateforme.", 501)

    async def wifi_forget(self, ssid: str) -> None:
        raise DeviceError("unsupported", "L'oubli d'un réseau Wi-Fi n'est pas possible ici.", 501)

    # --- réglages du système -----------------------------------------------
    async def open_system_settings(self, target: str) -> None:
        """Ouvre l'écran de réglages du système (« wifi », « bluetooth », « sound ») sur la machine."""
        raise DeviceError("unsupported", "Les réglages du système ne peuvent pas être ouverts depuis Bobine ici.", 501)

    async def wifi_interface_subnet(self) -> str | None:
        """Sous-réseau IPv4 (CIDR) de l'interface Wi-Fi, pour détecter un appareil connecté par ce seul réseau."""
        return None


class NullDriver(DeviceDriver):
    """Pilote des plateformes sans implémentation : tout est « non pris en charge », rien ne plante."""

    name = "none"

    def __init__(self, reason: str = "Cette plateforme n'est pas encore prise en charge.") -> None:
        super().__init__()
        self.reason = reason

    async def capabilities(self) -> dict[str, dict[str, Any]]:
        return no_capabilities(self.reason)

    async def audio_list(self) -> dict[str, Any]:
        return unsupported(self.reason)

    async def bluetooth_status(self) -> dict[str, Any]:
        return unsupported(self.reason)

    async def wifi_status(self) -> dict[str, Any]:
        return unsupported(self.reason)


__all__: list[str] = [
    "CAPABILITY_KEYS",
    "SCOPES",
    "ChangeCallback",
    "DeviceDriver",
    "DeviceError",
    "NullDriver",
    "no_capabilities",
    "unsupported",
]
