"""Répondeur mDNS embarqué (bibliothèque `zeroconf`), publiant
`bobine.local` sur le réseau local.

Sur l'appliance Linux headless, ce rôle est déjà tenu par `avahi-daemon`
(cf. `install.sh` §mdns-redirect) — ce module n'y est donc PAS activé, pour
éviter deux répondeurs concurrents sur le même nom. Il ne sert que sur les
profils où aucun service mDNS système n'est garanti actif : Windows en
particulier n'a pas de répondeur mDNS actif par défaut (CDC §5.5).

Best-effort et non bloquant : si l'enregistrement échoue (port occupé,
pare-feu, etc.), l'admin reste de toute façon accessible via `localhost`
ou l'IP locale (déjà affichées dans Réglages) — on log un avertissement et
on continue plutôt que d'empêcher le démarrage du backend pour ça.
"""

import logging
import platform
import socket
import threading

logger = logging.getLogger(__name__)

MDNS_HOSTNAME = "bobine"

_zeroconf = None
_service_info = None
_registration_lock = threading.Lock()


def _should_self_publish() -> bool:
    """True uniquement là où aucun démon mDNS système n'est déjà garanti
    actif — aujourd'hui : tout ce qui n'est pas l'appliance Linux headless
    (avahi-daemon, installé et configuré par install.sh)."""
    from app.utils.deployment import get_deployment_profile
    return get_deployment_profile() != "linux-headless"


def _register_sync(port: int) -> None:
    """Partie bloquante (résolution IP + I/O réseau `zeroconf`), exécutée
    hors du thread principal par `start_mdns_responder` — un environnement
    où le multicast UDP est indisponible ou bridé (constaté en sandbox : la
    seule inscription a pris ~11s avant d'échouer) ne doit jamais retarder
    le démarrage du reste du backend."""
    global _zeroconf, _service_info
    try:
        from zeroconf import ServiceInfo, Zeroconf
    except ImportError:
        logger.warning("Bibliothèque 'zeroconf' absente — bobine.local ne sera pas publié par le backend.")
        return

    try:
        # Adresse IP locale (même technique que _get_local_ip dans
        # routers/settings.py : connect() UDP sans envoi réel de paquet).
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        finally:
            s.close()

        zc = Zeroconf()
        info = ServiceInfo(
            "_http._tcp.local.",
            "Bobine._http._tcp.local.",
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            server=f"{MDNS_HOSTNAME}.local.",
        )
        zc.register_service(info)
        with _registration_lock:
            _zeroconf, _service_info = zc, info
        logger.info(f"mDNS : '{MDNS_HOSTNAME}.local' publié ({local_ip}:{port}, profil {platform.system()}).")
    except Exception as e:
        logger.warning(f"Échec de la publication mDNS (bobine.local restera indisponible) : {e!r}")


def start_mdns_responder(port: int) -> None:
    """À appeler une fois au démarrage du backend (lifespan). No-op sur le
    profil headless (avahi s'en charge déjà). Lance l'inscription réseau
    dans un thread séparé : ne bloque jamais le démarrage du reste du
    backend, quelle que soit la durée/issue de l'opération réseau."""
    if not _should_self_publish():
        return
    threading.Thread(target=_register_sync, args=(port,), daemon=True, name="bobine-mdns").start()


def stop_mdns_responder() -> None:
    global _zeroconf, _service_info
    with _registration_lock:
        zc, info = _zeroconf, _service_info
        _zeroconf, _service_info = None, None
    if zc is not None:
        try:
            if info is not None:
                zc.unregister_service(info)
            zc.close()
        except Exception as e:
            logger.warning(f"Échec de l'arrêt propre du répondeur mDNS : {e!r}")
