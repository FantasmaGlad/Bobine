"""Client SOCKS5 minimal vers un proxy Tor : connexion, ouvreur urllib, sonde."""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import struct
import urllib.error
import urllib.request
from typing import Any

_PROBE_TIMEOUT = 2.0


_CONNECT_TIMEOUT = 30.0


_REPLY_ERRORS = {
    1: "défaillance générale", 2: "connexion interdite", 3: "réseau injoignable", 4: "hôte injoignable",
    5: "connexion refusée", 6: "durée de vie expirée", 7: "commande non prise en charge", 8: "type d'adresse refusé",
}


class TorUnavailable(urllib.error.URLError):
    """Tor est activé mais aucun proxy ne répond et aucun programme `tor` ne peut être lancé, ou il a échoué."""


def parse_proxy(value: str) -> tuple[str, int]:
    """`hôte:port` (IPv6 entre crochets) ; lève ValueError si l'adresse est invalide."""
    host, sep, port_text = value.strip().rpartition(":")
    host = host.strip("[]")
    if not sep or not host or not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
        raise ValueError("adresse du proxy Tor invalide (attendu hôte:port, par exemple 127.0.0.1:9050)")
    return host, int(port_text)


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise TorUnavailable("le proxy Tor a fermé la connexion")
        data += chunk
    return data


def open_socks_connection(proxy: tuple[str, int], host: str, port: int, timeout: float | None) -> socket.socket:
    try:
        sock = socket.create_connection(proxy, timeout=min(timeout or _CONNECT_TIMEOUT, _CONNECT_TIMEOUT))
    except OSError as exc:
        raise TorUnavailable(f"proxy Tor injoignable sur {proxy[0]}:{proxy[1]} ({exc})") from exc
    try:
        sock.settimeout(timeout)
        sock.sendall(b"\x05\x01\x00")
        if _recv_exact(sock, 2) != b"\x05\x00":
            raise TorUnavailable("le proxy n'accepte pas une connexion SOCKS5 sans authentification")
        try:
            address = ipaddress.ip_address(host)
            target = (b"\x01" if address.version == 4 else b"\x04") + address.packed
        except ValueError:
            encoded = host.encode("idna")
            target = b"\x03" + bytes([len(encoded)]) + encoded
        sock.sendall(b"\x05\x01\x00" + target + struct.pack(">H", port))
        _, status, _, atyp = _recv_exact(sock, 4)
        if status != 0:
            raise TorUnavailable(f"le proxy Tor refuse la connexion à {host} : {_REPLY_ERRORS.get(status, status)}")
        _recv_exact(sock, {1: 4, 4: 16}.get(atyp) or _recv_exact(sock, 1)[0])
        _recv_exact(sock, 2)
        return sock
    except BaseException:
        sock.close()
        raise


class _SocksHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args: Any, proxy: tuple[str, int], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._socks_proxy = proxy

    def connect(self) -> None:
        self.sock = open_socks_connection(self._socks_proxy, self.host, self.port, self.timeout)


class _SocksHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args: Any, proxy: tuple[str, int], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._socks_proxy = proxy

    def connect(self) -> None:
        sock = open_socks_connection(self._socks_proxy, self.host, self.port, self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _SocksHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, proxy: tuple[str, int]) -> None:
        super().__init__()
        self._proxy = proxy

    def http_open(self, req: urllib.request.Request):
        return self.do_open(lambda host, **kw: _SocksHTTPConnection(host, proxy=self._proxy, **kw), req)


class _SocksHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, proxy: tuple[str, int]) -> None:
        super().__init__(context=ssl.create_default_context())
        self._proxy = proxy

    def https_open(self, req: urllib.request.Request):
        return self.do_open(
            lambda host, **kw: _SocksHTTPSConnection(host, proxy=self._proxy, **kw), req, context=self._context,
        )


def build_opener(proxy: tuple[str, int]) -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _SocksHTTPHandler(proxy), _SocksHTTPSHandler(proxy))


def proxy_answers(proxy: tuple[str, int]) -> bool:
    try:
        with socket.create_connection(proxy, timeout=_PROBE_TIMEOUT) as sock:
            sock.settimeout(_PROBE_TIMEOUT)
            sock.sendall(b"\x05\x01\x00")
            return sock.recv(2) == b"\x05\x00"
    except OSError:
        return False
