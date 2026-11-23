"""Sorties de diffusion : une seule table, d'où viennent canaux, sorties radio, modes d'écran et capacités."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Output:
    id: str
    label: str
    radio_label: str
    radio_channel: str
    modes: tuple[str, ...]
    wired: bool = False
    coach: bool = False
    schedule_first: bool = False


OUTPUTS: tuple[Output, ...] = (
    Output("cable", "Câblé", "Radio câblée", "radio_cable", ("kiosk", "cinema", "radio", "signage"), wired=True, coach=True, schedule_first=True),
    Output("network", "Réseau 1", "Radio Réseau 1", "radio_network", ("kiosk", "cinema", "radio", "signage")),
    Output("network_2", "Réseau 2", "Radio Réseau 2", "radio_network_2", ("kiosk", "cinema", "radio", "signage")),
)

_BY_ID = {output.id: output for output in OUTPUTS}
_BY_RADIO = {output.radio_channel: output for output in OUTPUTS}

DEFAULT_OUTPUT = OUTPUTS[0]
WIRED_OUTPUT = next(output for output in OUTPUTS if output.wired)
DEFAULT_RADIO_CHANNEL = _BY_ID["network_2"].radio_channel


def get_output(output_id: str) -> Output | None:
    return _BY_ID.get(output_id)


def output_of_radio(radio_channel: str) -> Output | None:
    return _BY_RADIO.get(radio_channel)


def radio_channel_of(output_id: str) -> str:
    """Radio d'une sortie ; la radio par défaut pour une valeur inconnue."""
    output = _BY_ID.get(output_id)
    return output.radio_channel if output else DEFAULT_RADIO_CHANNEL


def display_modes() -> tuple[str, ...]:
    """Tous les modes d'écran, dans l'ordre de leur première apparition."""
    return tuple(dict.fromkeys(mode for output in OUTPUTS for mode in output.modes))
