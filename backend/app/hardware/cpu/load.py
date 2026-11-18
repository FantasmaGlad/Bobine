import logging
import os
import time

import psutil

logger = logging.getLogger(__name__)

_LAST_CPU_TIMES: tuple[float, float, float] = (0.0, 0.0, 0.0)
_LAST_SMOOTH_CPU_PCT: float = 0.0


def _clamp(pct: float) -> float:
    return round(min(100.0, max(0.0, pct)), 1)


def _from_proc_stat(now: float, last: tuple[float, float, float]):
    with open("/proc/stat", "r", encoding="utf-8") as f:
        line = f.readline()
    if not line.startswith("cpu "):
        return None
    parts = [float(x) for x in line.split()[1:]]
    idle = parts[3] + (parts[4] if len(parts) > 4 else 0.0)
    total = sum(parts)
    last_wall, last_total, last_idle = last
    pct = None
    if last_wall > 0 and total > last_total:
        pct = _clamp((1.0 - ((idle - last_idle) / (total - last_total))) * 100.0)
    return pct, (now, total, idle)


def _from_loadavg(now: float, last: tuple[float, float, float]):
    with open("/proc/loadavg", "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return None
    return _clamp(float(content.split()[0]) / (os.cpu_count() or 1) * 100.0), (now, 0.0, 0.0)


def _from_psutil(now: float, last: tuple[float, float, float]):
    value = psutil.cpu_percent(interval=None)
    return (round(value, 1), (now, 0.0, 0.0)) if value > 0.0 else None


def _from_own_process(now: float, last: tuple[float, float, float]):
    with open("/proc/self/stat", "r", encoding="utf-8") as f:
        parts = f.read().split()
    total_ticks = int(parts[13]) + int(parts[14])
    clk_tck = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", 100)) if hasattr(os, "sysconf") else 100
    last_wall, last_total, _ = last
    pct = None
    if last_wall > 0 and now > last_wall and last_total > 0:
        delta_sec, delta_ticks = now - last_wall, total_ticks - last_total
        if delta_sec > 0 and delta_ticks >= 0:
            pct = _clamp((delta_ticks / clk_tck) / delta_sec / (os.cpu_count() or 1) * 100.0)
    return pct, (now, total_ticks, 0.0)


_CPU_SOURCES = (
    ("/proc/stat", _from_proc_stat),
    ("/proc/loadavg", _from_loadavg),
    (None, _from_psutil),
    ("/proc/self/stat", _from_own_process),
)


def _measure(path: str | None, source, now: float, last: tuple[float, float, float]):
    if path is not None and not os.path.exists(path):
        return None
    try:
        return source(now, last)
    except Exception as exc:
        logger.debug("get_cpu_percent : %s", exc)
        return None


def get_cpu_percent() -> float:
    """Calcule la charge CPU globale du système de manière non bloquante et lissée."""
    global _LAST_CPU_TIMES, _LAST_SMOOTH_CPU_PCT
    now = time.time()
    if _LAST_CPU_TIMES[0] > 0 and (now - _LAST_CPU_TIMES[0]) < 1.5:
        return _LAST_SMOOTH_CPU_PCT
    for path, source in _CPU_SOURCES:
        result = _measure(path, source, now, _LAST_CPU_TIMES)
        if result is not None:
            pct, _LAST_CPU_TIMES = result
            if pct is not None:
                _LAST_SMOOTH_CPU_PCT = pct
            return _LAST_SMOOTH_CPU_PCT
    _LAST_CPU_TIMES = (now, 0.0, 0.0)
    return _LAST_SMOOTH_CPU_PCT
