"""Sondes de santé partagées par `/api/health` (chien de garde) et le diagnostic système."""
import psutil

KIOSK_PROCESS_NAMES = ("chromium", "chromium-browser", "chrome", "msedge", "google chrome")


def kiosk_process_alive() -> str:
    """Présence d'un processus de navigateur kiosque sur la machine (le
    backend tourne sur le même hôte). `psutil` (déjà une dépendance du
    projet) remplace `pgrep` — absent de Windows — ; fonctionne à l'identique sur
    Linux/Windows/macOS. Le nom de process macOS de Chrome est "Google
    Chrome" (avec espace) — `"google chrome"` couvre ce cas après le
    `.lower()` ci-dessous ; sans lui, aucun préfixe ne matchait "google
    chrome" et le kiosque macOS aurait toujours été rapporté "down". "unknown" si l'énumération des process échoue (rare — droits
    insuffisants)."""
    try:
        for proc in psutil.process_iter(["name"]):
            proc_name = (proc.info.get("name") or "").lower()
            if any(proc_name.startswith(name) for name in KIOSK_PROCESS_NAMES):
                return "ok"
    except Exception:
        return "unknown"
    return "down"
