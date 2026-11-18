import platform

from .guard import guarded


def _registry_name() -> str:
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
        value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
    return str(value or "").strip() or platform.processor() or ""


def cpu_name() -> str:
    return guarded(_registry_name) or platform.processor() or ""
