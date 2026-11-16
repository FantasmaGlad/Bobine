"""NetworkManager (nmcli) : état, recherche, connexion, oubli."""

from __future__ import annotations

import ipaddress
import shutil
import time
from typing import Any

from ..base import DeviceError, unsupported
from .parse.wifi import parse_known_wifi, parse_wifi_device, parse_wifi_list


class WifiMixin:
    async def _probe_wifi(self) -> str | None:
        if not shutil.which("nmcli"):
            return "NetworkManager (nmcli) n'est pas installé sur cette machine."
        try:
            device = await self._wifi_device(force=True)
        except DeviceError as exc:
            return exc.message
        return None if device else "Aucun adaptateur Wi-Fi détecté."

    async def _nmcli(self, *args: str, timeout: float = 15.0, stdin: str | None = None) -> str:
        code, out, err = await self._run("nmcli", *args, timeout=timeout, stdin=stdin)
        if code != 0:
            raise DeviceError(*_nmcli_error(err or out))
        return out

    async def _known_wifi(self) -> list[dict[str, str]]:
        return parse_known_wifi(await self._nmcli("-t", "-f", "NAME,UUID,TYPE", "connection", "show", timeout=8))

    async def _wifi_device(self, force: bool = False) -> dict[str, str] | None:
        now = time.monotonic()
        if not force and now - self._wifi_device_cache[0] < 10:
            return self._wifi_device_cache[1]
        out = await self._nmcli("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev", "status", timeout=8)
        device = parse_wifi_device(out)
        self._wifi_device_cache = (now, device)
        return device

    async def wifi_status(self) -> dict[str, Any]:
        reason = await self._probe_wifi()
        if reason:
            return unsupported(reason)
        device = await self._wifi_device()
        assert device is not None
        radio = (await self._nmcli("radio", "wifi", timeout=6)).strip() == "enabled"
        known_rows = await self._known_wifi()
        known_names = {k["name"] for k in known_rows}
        networks: list[dict[str, Any]] = []
        if radio:
            out = await self._nmcli("-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,FREQ", "dev", "wifi", "list", "ifname", device["device"], "--rescan", "no", timeout=10)
            networks = parse_wifi_list(out, known_names)
        current = next((n for n in networks if n["in_use"]), None)
        ip = None
        if current:
            ip_out = await self._nmcli("-t", "-g", "IP4.ADDRESS", "dev", "show", device["device"], timeout=6)
            ip = (ip_out.strip().splitlines() or [""])[0].split("/")[0] or None
            current = {**current, "ip": ip}
        return {
            "supported": True,
            "enabled": radio,
            "interface": device["device"],
            "state": device["state"],
            "current": current,
            "networks": networks,
            "known": [k["name"] for k in known_rows],
        }

    async def wifi_set_power(self, on: bool) -> None:
        await self._nmcli("radio", "wifi", "on" if on else "off", timeout=8)
        self._invalidate_probe()
        self._emit("wifi")

    async def wifi_scan(self) -> None:
        device = await self._wifi_device()
        if not device:
            raise DeviceError("no_adapter", "Aucun adaptateur Wi-Fi détecté.", 501)
        try:
            await self._nmcli("dev", "wifi", "rescan", "ifname", device["device"], timeout=10)
        except DeviceError as exc:
            if exc.code != "wifi_busy":
                raise
        self._emit("wifi")

    async def wifi_current_connection(self) -> str | None:
        device = await self._wifi_device(force=True)
        connection = (device or {}).get("connection", "")
        return connection if connection and connection != "--" else None

    async def wifi_connect(self, ssid: str, password: str | None) -> None:
        device = await self._wifi_device()
        if not device:
            raise DeviceError("no_adapter", "Aucun adaptateur Wi-Fi détecté.", 501)
        known = {k["name"] for k in await self._known_wifi()}
        if ssid in known and not password:
            await self._nmcli("-w", "30", "connection", "up", "id", ssid, "ifname", device["device"], timeout=40)
        elif password:
            await self._nmcli("--ask", "-w", "30", "dev", "wifi", "connect", ssid, "ifname", device["device"], timeout=40, stdin=password + "\n")
        else:
            await self._nmcli("-w", "30", "dev", "wifi", "connect", ssid, "ifname", device["device"], timeout=40)
        self._emit("wifi")

    async def wifi_activate(self, connection: str) -> None:
        device = await self._wifi_device()
        args = ["-w", "30", "connection", "up", "id", connection]
        if device:
            args += ["ifname", device["device"]]
        await self._nmcli(*args, timeout=40)
        self._emit("wifi")

    async def wifi_forget(self, ssid: str) -> None:
        await self._nmcli("connection", "delete", "id", ssid, timeout=10)
        self._emit("wifi")

    async def wifi_interface_subnet(self) -> str | None:
        device = await self._wifi_device()
        if not device:
            return None
        try:
            out = await self._nmcli("-t", "-g", "IP4.ADDRESS", "dev", "show", device["device"], timeout=6)
            first = (out.strip().splitlines() or [""])[0]
            return str(ipaddress.ip_interface(first).network) if first else None
        except (DeviceError, ValueError):
            return None


def _nmcli_error(text: str) -> tuple[str, str, int]:
    message = (text or "").strip().splitlines()[-1] if (text or "").strip() else "NetworkManager a refusé l'opération."
    lowered = message.lower()
    if "secrets were required" in lowered or "password" in lowered or "802-1x" in lowered:
        return ("wifi_auth_failed", "Mot de passe incorrect ou réseau inaccessible.", 400)
    if "no network with ssid" in lowered:
        return ("not_found", "Ce réseau Wi-Fi n'est pas à portée.", 404)
    if "not authorized" in lowered or "permission" in lowered:
        return ("not_authorized", "Le compte qui exécute Bobine n'a pas le droit de gérer le Wi-Fi (polkit).", 403)
    if "scanning not allowed" in lowered or "rescan" in lowered:
        return ("wifi_busy", "Recherche déjà en cours.", 409)
    if "unknown connection" in lowered or "not found" in lowered:
        return ("not_found", "Réseau introuvable.", 404)
    if "timeout" in lowered or "timed out" in lowered:
        return ("timeout", "La connexion n'a pas abouti dans le délai imparti.", 504)
    return ("wifi_failed", message[:200], 502)
