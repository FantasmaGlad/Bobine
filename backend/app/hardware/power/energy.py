import time

from ..probe import _SERVICE_START_TIME

_CUMULATIVE_ENERGY_WH: float = 0.0
_LAST_ENERGY_SAMPLE_TIME: float = 0.0


def update_cumulative_energy(watts: float | None) -> None:
    """Met à jour l'énergie cumulée en Watt-heures (Wh)."""
    global _CUMULATIVE_ENERGY_WH, _LAST_ENERGY_SAMPLE_TIME
    now = time.time()
    if _LAST_ENERGY_SAMPLE_TIME > 0 and watts and watts > 0:
        delta_hours = (now - _LAST_ENERGY_SAMPLE_TIME) / 3600.0
        if 0 < delta_hours < 0.1:
            _CUMULATIVE_ENERGY_WH += watts * delta_hours
    _LAST_ENERGY_SAMPLE_TIME = now


def get_cumulative_energy_wh() -> float:
    return round(_CUMULATIVE_ENERGY_WH, 2)


def get_average_power_watts() -> float | None:
    now = time.time()
    runtime_hours = (now - _SERVICE_START_TIME) / 3600.0
    if runtime_hours > 0 and _CUMULATIVE_ENERGY_WH > 0:
        return round(_CUMULATIVE_ENERGY_WH / runtime_hours, 1)
    return None
