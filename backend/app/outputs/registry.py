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
    Output("network", "Réseau", "Radio réseau", "radio_network", ("kiosk", "cinema", "signage")),
)

_BY_ID = {output.id: output for output in OUTPUTS}
_BY_RADIO = {output.radio_channel: output for output in OUTPUTS}

DEFAULT_OUTPUT = OUTPUTS[0]
WIRED_OUTPUT = next(output for output in OUTPUTS if output.wired)
DEFAULT_RADIO_CHANNEL = _BY_ID["network"].radio_channel


def get_output(output_id: str) -> Output | None:
    return _BY_ID.get(output_id)


def output_of_radio(radio_channel: str) -> Output | None:
    return _BY_RADIO.get(radio_channel)


def display_modes() -> tuple[str, ...]:
    """Tous les modes d'écran, dans l'ordre de leur première apparition."""
    return tuple(dict.fromkeys(mode for output in OUTPUTS for mode in output.modes))
