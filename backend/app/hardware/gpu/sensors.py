import psutil


def temperature() -> float | None:
    temps = psutil.sensors_temperatures() or {}
    return next((round(temps[k][0].current, 1) for k in ("amdgpu", "nouveau", "nvidia") if temps.get(k)), None)
