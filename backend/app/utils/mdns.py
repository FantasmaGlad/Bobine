"""Répondeur mDNS embarqué (bibliothèque `zeroconf`), publiant
`bobine.local` sur le réseau local.

Sur l'appliance Linux headless, ce rôle est déjà tenu par `avahi-daemon`,
configuré par `install.sh` pour publier précisément `bobine.local` (cf.
`install.sh` §mdns-redirect) — ce module n'y est donc PAS activé, pour
éviter deux répondeurs concurrents sur le même nom. Un Linux **desktop**
(Ubuntu/Fedora typique) a lui aussi très souvent un `avahi-daemon` déjà
actif nativement (dépendance usuelle de CUPS/NetworkManager) — détecté par
`_avahi_daemon_active()` et exclu au même titre pour éviter un conflit de
nom (deux répondeurs sur `bobine.local`, l'un d'eux se repliant
silencieusement sur `bobine-2.local` par résolution RFC 6762 sans que rien
ne le signale). Il s'active sur tous les autres profils, Windows ET macOS
inclus : contrairement à ce que l'on pourrait croire (« Bonjour est actif
nativement »), le service Bonjour natif de macOS publie le nom d'hôte
*configuré de la machine* (ex. « Mac-de-Jean.local »), pas spécifiquement
« bobine.local » — sans ce répondeur embarqué, rien ne publierait ce nom
précis sur macOS, exactement comme sur Windows.

Boucle de fond avec re-annonce périodique et nouvelles tentatives en cas
d'échec (cf. `_run_loop`) — l'ancienne version ne s'enregistrait qu'UNE
SEULE fois au démarrage (thread fire-and-forget) : un changement d'IP
DHCP/Wi-Fi après coup, ou un premier essai raté (multicast indisponible/
bridé, ~11s observés avant échec en sandbox), laissait `bobine.local`
durablement injoignable jusqu'au redémarrage complet du backend — cause
racine confirmée du constat "le mDNS ne marche pas très régulièrement".

Best-effort et non bloquant : si l'enregistrement échoue durablement (port
occupé, pare-feu...), l'admin reste de toute façon accessible via
`localhost` ou l'IP locale (déjà affichées dans Réglages, cf.
`get_status()` ci-dessous consommé par `GET /api/settings` pour refléter
l'échec plutôt que d'afficher `bobine.local` comme s'il fonctionnait).
"""

import logging
import platform
import socket
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MDNS_HOSTNAME = "bobine"

# Ré-annonce périodique même en cas de succès : couvre un changement d'IP
# DHCP/Wi-Fi survenu après le premier enregistrement, que `zeroconf` seul ne
# détecte jamais tout seul (ServiceInfo.addresses reste figé sinon).
_REANNOUNCE_INTERVAL_SECONDS = 5 * 60
# Délai croissant entre tentatives après un échec — jamais d'abandon
# silencieux définitif comme l'ancienne version (un seul essai, puis plus
# rien jusqu'au redémarrage du process).
_RETRY_DELAYS_SECONDS = (2.0, 5.0, 10.0, 30.0, 60.0)
_AVAHI_SOCKET_PATH = Path("/var/run/avahi-daemon/socket")

_zeroconf = None
_service_info = None
_last_announced_ip: str | None = None
_state_lock = threading.Lock()
_stop_event = threading.Event()
_thread: threading.Thread | None = None
_status: dict[str, Any] = {"state": "pending", "detail": None}


def _set_status(state: str, detail: str | None = None) -> None:
    with _state_lock:
        _status["state"] = state
        _status["detail"] = detail


def get_status() -> dict[str, Any]:
    """État courant du répondeur mDNS — consommé par `GET /api/settings`
    (bloc `network`) pour que l'UI puisse signaler que `bobine.local` est
    réellement indisponible plutôt que d'afficher cette URL comme si elle
    fonctionnait systématiquement. `state` vaut l'un de : "ok" (publié avec
    succès), "failed" (dernière tentative en échec, nouvel essai
    programmé), "disabled" (profil headless, délégué à avahi-daemon
    système), "external" (Linux desktop, avahi-daemon natif détecté actif),
    "unavailable" (bibliothèque `zeroconf` absente), "pending" (thread pas
    encore passé une première fois)."""
    with _state_lock:
        return dict(_status)


def _avahi_daemon_active() -> bool:
    """Détecte un `avahi-daemon` déjà actif nativement sur ce Linux desktop
    (dépendance fréquente de CUPS/NetworkManager sur une distribution
    classique type Ubuntu/Fedora) — présence du socket Unix qu'il expose en
    permanence tant qu'il tourne, plutôt qu'un appel `systemctl` (coûteux,
    indisponible en session non systemd, et nécessitant un parsing de
    sortie fragile)."""
    try:
        return _AVAHI_SOCKET_PATH.exists()
    except OSError:
        return False


def _should_self_publish() -> bool:
    """True uniquement là où aucun démon mDNS système n'est déjà garanti
    actif : ni l'appliance Linux headless (avahi-daemon installé et
    configuré par install.sh), ni un Linux desktop où un avahi-daemon
    natif tourne déjà (cf. `_avahi_daemon_active`)."""
    from app.utils.deployment import get_deployment_profile

    profile = get_deployment_profile()
    if profile == "linux-headless":
        return False
    if profile == "linux-desktop" and _avahi_daemon_active():
        return False
    return True


def _local_ip() -> str | None:
    """Même technique que `_get_local_ip` dans `routers/settings.py`
    (connect() UDP sans envoi réel de paquet) — dupliquée ici à dessein :
    ce module tourne dans son propre thread de fond, indépendant du cycle
    de requêtes FastAPI, et ne doit dépendre d'aucun état de la couche
    HTTP."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.2)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _register_or_update(zc: Any, port: int) -> str:
    """Enregistre le service, ou le met à jour (`update_service`) si l'IP
    locale a changé depuis la dernière annonce réussie — c'est ce second
    cas qui manquait entièrement avant ce correctif, `ServiceInfo.addresses`
    restant sinon figé sur l'IP du tout premier enregistrement. Renvoie
    l'IP effectivement annoncée ; lève si aucune IP locale n'est résolvable
    (ex. aucune interface réseau active pour le moment)."""
    global _service_info, _last_announced_ip
    from zeroconf import ServiceInfo

    local_ip = _local_ip()
    if not local_ip:
        raise RuntimeError("aucune adresse IP locale résolvable pour le moment")

    with _state_lock:
        already_registered = _service_info is not None
        unchanged = already_registered and local_ip == _last_announced_ip

    if unchanged:
        return local_ip

    info = ServiceInfo(
        "_http._tcp.local.",
        "Bobine._http._tcp.local.",
        addresses=[socket.inet_aton(local_ip)],
        port=port,
        server=f"{MDNS_HOSTNAME}.local.",
    )
    if already_registered:
        zc.update_service(info)
    else:
        zc.register_service(info)
    with _state_lock:
        _service_info = info
        _last_announced_ip = local_ip
    return local_ip


def _run_loop(port: int) -> None:
    """Boucle de fond : ré-essaie avec un délai croissant après un échec,
    puis ré-annonce périodiquement même en cas de succès continu (pour
    capter un changement d'IP DHCP/Wi-Fi). Remplace l'ancien
    `_register_sync` fire-and-forget (un seul essai, jamais retenté)."""
    global _zeroconf

    try:
        from zeroconf import Zeroconf
    except ImportError:
        logger.warning("Bibliothèque 'zeroconf' absente — bobine.local ne sera pas publié par le backend.")
        _set_status("unavailable", "bibliothèque zeroconf absente")
        return

    zc = Zeroconf()
    with _state_lock:
        _zeroconf = zc

    attempt = 0
    while not _stop_event.is_set():
        try:
            announced_ip = _register_or_update(zc, port)
            if _status.get("state") != "ok":
                logger.info(f"mDNS : '{MDNS_HOSTNAME}.local' publié ({announced_ip}:{port}, profil {platform.system()}).")
            _set_status("ok")
            attempt = 0
            if _stop_event.wait(_REANNOUNCE_INTERVAL_SECONDS):
                break
        except Exception as e:
            _set_status("failed", str(e))
            delay = _RETRY_DELAYS_SECONDS[min(attempt, len(_RETRY_DELAYS_SECONDS) - 1)]
            logger.warning(
                f"Échec de la publication mDNS (tentative {attempt + 1}) : {e!r} — nouvel essai dans {delay:.0f}s."
            )
            attempt += 1
            if _stop_event.wait(delay):
                break


def start_mdns_responder(port: int) -> None:
    """À appeler une fois au démarrage du backend (lifespan). No-op sur le
    profil headless ou un Linux desktop avec avahi-daemon natif détecté
    (déjà pris en charge par le système). Lance la boucle d'enregistrement/
    ré-annonce dans un thread dédié : ne bloque jamais le démarrage du reste
    du backend, quelle que soit la durée/issue des tentatives réseau."""
    global _thread
    if not _should_self_publish():
        from app.utils.deployment import get_deployment_profile

        state = "disabled" if get_deployment_profile() == "linux-headless" else "external"
        _set_status(state)
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_run_loop, args=(port,), daemon=True, name="bobine-mdns")
    _thread.start()


def stop_mdns_responder() -> None:
    global _zeroconf, _service_info, _last_announced_ip, _thread
    _stop_event.set()
    with _state_lock:
        zc, info = _zeroconf, _service_info
        _zeroconf, _service_info, _last_announced_ip = None, None, None
    if zc is not None:
        try:
            if info is not None:
                zc.unregister_service(info)
            zc.close()
        except Exception as e:
            logger.warning(f"Échec de l'arrêt propre du répondeur mDNS : {e!r}")
    _thread = None
