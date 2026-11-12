"""Client HTTP de l'API locale : requêtes, envois et téléchargements, port et délai par défaut."""

from __future__ import annotations

import argparse
import http.client
import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from app.api.contract import DEFAULT_PORT
from .core import _REFUSAL_STATUSES, DEFAULT_TIMEOUT, EXIT_ERROR, EXIT_REFUSED, EXIT_UNREACHABLE, EXIT_USAGE, CliError, Output


class Client:
    def __init__(self, host: str, port: int, out: Output, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.base = f"http://{host}:{port}"
        self.out, self.timeout = out, timeout

    def request(
        self, method: str, path: str, *, query: dict | None = None, body: Any = None,
        accept_status: frozenset[int] = frozenset(),
    ) -> Any:
        url = self.base + path + (f"?{urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})}" if query else "")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        self.out.log(1, f"{method} {url}")
        if data is not None:
            self.out.log(2, f"> {data.decode('utf-8')}")
        started = time.monotonic()
        try:
            req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"} if data else {})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw, status = exc.read(), exc.code
        except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as exc:
            raise CliError(f"Bobine injoignable sur {self.base} ({getattr(exc, 'reason', exc)}).", EXIT_UNREACHABLE) from exc
        self.out.log(2, f"< {status} en {1000 * (time.monotonic() - started):.0f} ms : {raw[:2000].decode('utf-8', 'replace')}")
        return self._interpret(status, raw, url, accept_status)

    def _interpret(self, status: int, raw: bytes, url: str, accept_status: frozenset[int] = frozenset()) -> Any:
        try:
            payload = json.loads(raw) if raw else None
        except ValueError:
            payload = raw.decode("utf-8", "replace")
        if status >= 400 and status not in accept_status:
            detail = payload.get("detail") if isinstance(payload, dict) else payload
            if isinstance(detail, dict):
                message = detail.get("message") or detail.get("code") or f"réponse {status}"
            elif isinstance(detail, list):
                message = " ; ".join(str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in detail)
            else:
                message = str(detail) if detail else f"réponse {status}"
            if isinstance(detail, dict) and detail.get("allowed"):
                message += " Admis : " + ", ".join(map(str, detail["allowed"]))
            errors = detail.get("errors") if isinstance(detail, dict) else None
            if errors:
                message = message + "\n" + "\n".join(f"  - {e}" for e in errors)
            code = EXIT_REFUSED if status in _REFUSAL_STATUSES else EXIT_USAGE if status in (400, 422) else EXIT_ERROR
            raise CliError(f"Refusé ({status}) : {message}", code, payload)
        if payload is not None and not isinstance(payload, (dict, list)):
            raise CliError(f"réponse non JSON ({status}) de {url} : {raw[:200]!r}", EXIT_ERROR, payload)
        return payload

    def upload(self, path: str, files: list[tuple[str, Path]], fields: dict[str, str] | None = None) -> Any:
        """Envoie des fichiers en multipart sans les charger en mémoire (une vidéo peut peser plusieurs Gio)."""
        boundary = "bobine" + uuid.uuid4().hex
        parts: list[bytes | Path] = []
        for name, value in (fields or {}).items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))
        for name, file in files:
            kind = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            filename = "".join(
                "_" if ch in '"\\\r\n' or ord(ch) < 32 or ord(ch) == 127 else ch
                for ch in file.name
            )
            parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                          f"Content-Type: {kind}\r\n\r\n").encode("utf-8"))
            parts.append(file)
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        try:
            length = sum(len(part) if isinstance(part, bytes) else part.stat().st_size for part in parts)
        except OSError as exc:
            raise CliError(f"fichier illisible : {exc}", EXIT_USAGE) from exc
        url = self.base + path
        self.out.log(1, f"POST {url} ({len(files)} fichier(s), {length} octets)")
        parsed = urllib.parse.urlsplit(url)
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=self.timeout)
        try:
            connection.putrequest("POST", parsed.path)
            connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
            connection.putheader("Content-Length", str(length))
            connection.endheaders()
            for part in parts:
                if isinstance(part, bytes):
                    connection.send(part)
                else:
                    with part.open("rb") as handle:
                        while chunk := handle.read(1 << 20):
                            connection.send(chunk)
            response = connection.getresponse()
            raw, status = response.read(), response.status
        except (OSError, http.client.HTTPException) as exc:
            raise CliError(f"Bobine injoignable sur {self.base} ({getattr(exc, 'reason', exc)}).", EXIT_UNREACHABLE) from exc
        finally:
            connection.close()
        return self._interpret(status, raw, url)

    def download(self, path: str, destination: Path) -> int:
        """Enregistre une réponse binaire (sauvegarde) dans `destination` ; renvoie sa taille."""
        url = self.base + path
        self.out.log(1, f"GET {url}")
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=self.timeout) as response:
                with destination.open("xb") as handle:
                    size = 0
                    while chunk := response.read(1 << 20):
                        handle.write(chunk)
                        size += len(chunk)
            return size
        except urllib.error.HTTPError as exc:
            self._interpret(exc.code, exc.read(), url)
            raise CliError(f"réponse {exc.code} de {url}", EXIT_ERROR) from exc
        except FileExistsError as exc:
            raise CliError(f"{destination} existe déjà : choisir un autre nom (rien n'est écrasé).", EXIT_USAGE) from exc
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            destination.unlink(missing_ok=True)
            raise CliError(f"Bobine injoignable sur {self.base} ({getattr(exc, 'reason', exc)}).", EXIT_UNREACHABLE) from exc


def local_version() -> str:
    try:
        from app.utils.version import get_app_version

        return get_app_version()
    except Exception:  # noqa: BLE001 — la version ne doit jamais empêcher la commande de répondre
        return "inconnue"


def _timeout(args: argparse.Namespace) -> float:
    raw = args.timeout if args.timeout is not None else os.environ.get("BOBINE_TIMEOUT")
    try:
        value = float(raw) if raw not in (None, "") else DEFAULT_TIMEOUT
    except ValueError:
        raise CliError(f"délai invalide : {raw!r} (secondes, par exemple 10).", EXIT_USAGE) from None
    if not 0 < value <= 3600:
        raise CliError(f"délai invalide : {value:g} (entre 0 et 3600 secondes).", EXIT_USAGE)
    return value


def _default_port() -> int:
    raw = os.environ.get("BOBINE_PORT")
    if raw:
        try:
            port = int(raw)
        except ValueError as exc:
            raise CliError(f"BOBINE_PORT invalide : {raw!r} (entier attendu).", EXIT_USAGE) from exc
        if not 1 <= port <= 65535:
            raise CliError(f"BOBINE_PORT hors bornes : {port} (1 à 65535).", EXIT_USAGE)
        return port
    try:
        from app.utils.port import current_port

        return current_port()
    except Exception:  # noqa: BLE001 — sans fichier d'exécution lisible, le port par défaut de Bobine
        return DEFAULT_PORT
