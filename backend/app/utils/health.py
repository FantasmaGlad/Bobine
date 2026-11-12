"""Sondes de santé partagées par `/api/health` (chien de garde) et le diagnostic système."""
import psutil

KIOSK_PROCESS_NAMES = ("chromium", "chromium-browser", "chrome", "msedge", "google chrome")


def kiosk_process_alive() -> str:
    """Présence d'un processus de navigateur kiosque sur la machine (le backend tourne sur le même hôte)."""
    try:
        for proc in psutil.process_iter(["name"]):
            proc_name = (proc.info.get("name") or "").lower()
            if any(proc_name.startswith(name) for name in KIOSK_PROCESS_NAMES):
                return "ok"
    except Exception:
        return "unknown"
    return "down"
