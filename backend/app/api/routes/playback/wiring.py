"""Câblage des moteurs de lecture au chargement : nombre d'écrans par canal et fin de piste radio côté serveur."""
from app.utils.ws_manager import manager as ws_manager

from .core import playback_managers, radio_managers
from .radio_commands import _radio_track_end_fallback


def _make_radio_track_end_fallback(radio_channel: str):
    """Filet de sécurité serveur de fin de piste d'UNE sortie radio : il passe par la même règle que la commande
    (rappels « toutes les N musiques »). Fabrique plutôt que lambda partagée : chaque moteur est lié à SA sortie."""
    async def _handler(track_id: int | None) -> None:
        await _radio_track_end_fallback(radio_channel, track_id)
    return _handler


# Démarrage synchronisé seulement s'il y a au moins deux écrans à caler sur le canal : un seul répond tout de suite.
for _manager in playback_managers.values():
    _manager.display_counter = ws_manager.kiosk_count
for _radio_channel, _radio_manager in radio_managers.items():
    _radio_manager.display_counter = ws_manager.kiosk_count
    _radio_manager.track_end_handler = _make_radio_track_end_fallback(_radio_channel)
