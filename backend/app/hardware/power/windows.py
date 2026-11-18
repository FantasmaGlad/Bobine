def desktop_watts(cpu_pct: float, nb_cores: int) -> float:
    base_desktop = 28.0 + min(25.0, max(0.0, (nb_cores - 4) * 2.5))
    active_desktop = base_desktop + (cpu_pct / 100.0) * (nb_cores * 4.5)
    return round(min(450.0, max(20.0, active_desktop)), 1)
