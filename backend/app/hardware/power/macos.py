import subprocess

from ..cpu import get_cpu_percent


def battery_power() -> float | None:
    out = subprocess.check_output(["ioreg", "-rc", "AppleSmartBattery"], text=True, timeout=1)
    volt = None
    amp = None
    is_charging = False
    external_connected = False
    for line in out.splitlines():
        if '"Voltage" =' in line:
            volt = int(line.split("=", 1)[1].strip())
        elif '"Amperage" =' in line:
            amp = int(line.split("=", 1)[1].strip())
        elif '"IsCharging" =' in line:
            is_charging = "Yes" in line or "true" in line.lower()
        elif '"ExternalConnected" =' in line:
            external_connected = "Yes" in line or "true" in line.lower()

    base_mac_w = 4.5 + (get_cpu_percent() / 100.0) * 22.0

    if external_connected:
        if is_charging and amp and amp > 0 and volt and volt > 0:
            return round((volt * amp) / 1_000_000.0 + base_mac_w, 1)
        return round(base_mac_w, 1)
    if volt and amp and volt > 0 and amp != 0:
        watts = (volt * abs(amp)) / 1_000_000.0
        if 0.5 <= watts <= 150.0:
            return round(watts, 1)
    return None


def desktop_watts(cpu_pct: float, nb_cores: int) -> float:
    base_macmini = 6.5 + min(8.0, max(0.0, (nb_cores - 4) * 1.0))
    active_macmini = base_macmini + (cpu_pct / 100.0) * (nb_cores * 3.0)
    return round(min(120.0, max(5.0, active_macmini)), 1)
