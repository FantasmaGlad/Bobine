"""Pilote Linux : PipeWire (audio), BlueZ par D-Bus (Bluetooth), NetworkManager (Wi-Fi).

* Audio : `pw-dump` (lecture JSON) et `wpctl` (volume, sortie par défaut) — sans dépendance Python.
* Bluetooth : `dbus-fast` (Python pur, asynchrone) sur le bus système ; Bobine enregistre un agent
  d'appairage BlueZ (`org.bluez.Agent1`) pour confirmer les codes depuis l'interface.
* Wi-Fi : `nmcli` en mode terse (front-end officiel de NetworkManager) ; les mots de passe sont
  transmis sur l'entrée standard (`--ask`), JAMAIS en argument (visible dans `ps`) ni journalisés.

Aucun appel ne lève d'exception brute : tout est converti en `DeviceError` ou `unsupported()`.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import shutil
import time
from typing import Any, Awaitable, Callable

from .base import CAPABILITY_KEYS, DeviceDriver, DeviceError, unsupported
from .linux_parse import (
    bluez_device_path,
    is_valid_mac,
    parse_bluez_objects,
    parse_known_wifi,
    parse_pw_dump,
    parse_wifi_device,
    parse_wifi_list,
    parse_wpctl_volume,
    split_terse,
)

logger = logging.getLogger(__name__)

# (code retour, stdout, stderr)
CommandResult = tuple[int, str, str]
Runner = Callable[..., Awaitable[CommandResult]]

_BLUEZ = "org.bluez"
_AGENT_PATH = "/org/bobine/agent"
_PAIR_PROMPT_TIMEOUT = 60.0
_PROBE_TTL = 30.0


async def run_command(*args: str, timeout: float = 10.0, stdin: str | None = None) -> CommandResult:
    """Exécute une commande sans shell, avec délai d'expiration et environnement stable (`LC_ALL=C`)."""
    env = dict(os.environ, LC_ALL="C", LANG="C")
    runtime_dir = f"/run/user/{os.getuid()}" if hasattr(os, "getuid") else ""
    if not env.get("XDG_RUNTIME_DIR") and runtime_dir and os.path.isdir(runtime_dir):
        env["XDG_RUNTIME_DIR"] = runtime_dir  # service sans session : cible la session PipeWire de l'utilisateur
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError as exc:
        raise DeviceError("tool_missing", f"Outil système introuvable : {args[0]}", 501) from exc
    except OSError as exc:
        raise DeviceError("tool_failed", f"Impossible de lancer {args[0]} : {exc.strerror or exc}", 502) from exc
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(stdin.encode() if stdin is not None else None), timeout=timeout
        )
    except asyncio.TimeoutError as exc:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        raise DeviceError("timeout", f"{args[0]} n'a pas répondu dans le délai imparti.", 504) from exc
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


class LinuxDriver(DeviceDriver):
    name = "linux"

    def __init__(self, runner: Runner = run_command) -> None:
        super().__init__()
        self._run = runner
        self._bus: Any = None
        self._bus_lock = asyncio.Lock()
        self._agent: Any = None
        self._pending: dict[str, Any] | None = None
        self._pending_future: asyncio.Future[bool] | None = None
        self._pairing: dict[str, Any] | None = None
        self._probe_cache: tuple[float, dict[str, dict[str, Any]]] | None = None
        self._wifi_device_cache: tuple[float, dict[str, str] | None] = (0.0, None)

    # ------------------------------------------------------------------ cycle de vie
    async def stop(self) -> None:
        bus, self._bus = self._bus, None
        if bus is not None:
            try:
                bus.disconnect()
            except Exception:  # fermeture au mieux
                pass

    # ------------------------------------------------------------------ capacités
    async def capabilities(self) -> dict[str, dict[str, Any]]:
        now = time.monotonic()
        if self._probe_cache and now - self._probe_cache[0] < _PROBE_TTL:
            return self._probe_cache[1]
        caps: dict[str, dict[str, Any]] = {k: {"supported": False, "reason": ""} for k in CAPABILITY_KEYS}

        audio_reason = await self._probe_audio()
        for key in ("audio_list", "audio_set_default", "audio_set_volume"):
            caps[key] = {"supported": audio_reason is None}
            if audio_reason:
                caps[key]["reason"] = audio_reason

        bt_reason = await self._probe_bluetooth()
        for key in ("bluetooth_status", "bluetooth_power", "bluetooth_scan", "bluetooth_pair", "bluetooth_connect", "bluetooth_forget"):
            caps[key] = {"supported": bt_reason is None}
            if bt_reason:
                caps[key]["reason"] = bt_reason

        wifi_reason = await self._probe_wifi()
        for key in ("wifi_status", "wifi_power", "wifi_scan", "wifi_connect", "wifi_forget"):
            caps[key] = {"supported": wifi_reason is None}
            if wifi_reason:
                caps[key]["reason"] = wifi_reason

        caps["system_settings"] = {"supported": False, "reason": "Non applicable sur ce système : utilisez cet écran."}
        self._probe_cache = (now, caps)
        return caps

    def _invalidate_probe(self) -> None:
        self._probe_cache = None

    async def _probe_audio(self) -> str | None:
        if not (shutil.which("pw-dump") and shutil.which("wpctl")):
            return "PipeWire (pw-dump, wpctl) n'est pas installé sur cette machine."
        try:
            code, _, _ = await self._run("wpctl", "status", timeout=4)
        except DeviceError as exc:
            return exc.message
        return None if code == 0 else "PipeWire ne répond pas pour le compte qui exécute Bobine."

    async def _probe_bluetooth(self) -> str | None:
        try:
            from dbus_fast import BusType  # noqa: F401
        except ImportError:
            return "Le module dbus-fast n'est pas installé."
        try:
            await self._ensure_bus()
            await self._bluez_objects()
        except DeviceError as exc:
            return exc.message
        status = await self._bluetooth_snapshot()
        if status["adapter_path"] is None:
            return "Aucun adaptateur Bluetooth détecté."
        return None

    async def _probe_wifi(self) -> str | None:
        if not shutil.which("nmcli"):
            return "NetworkManager (nmcli) n'est pas installé sur cette machine."
        try:
            device = await self._wifi_device(force=True)
        except DeviceError as exc:
            return exc.message
        return None if device else "Aucun adaptateur Wi-Fi détecté."

    # ------------------------------------------------------------------ audio
    async def _audio_sinks(self) -> dict[str, Any]:
        code, out, err = await self._run("pw-dump", timeout=8)
        if code != 0:
            raise DeviceError("audio_unavailable", (err.strip() or "PipeWire ne répond pas.")[:200], 502)
        try:
            return parse_pw_dump(json.loads(out))
        except (ValueError, KeyError, TypeError) as exc:
            raise DeviceError("audio_unavailable", "Réponse PipeWire illisible.", 502) from exc

    async def audio_list(self) -> dict[str, Any]:
        reason = await self._probe_audio()
        if reason:
            return unsupported(reason)
        data = await self._audio_sinks()

        async def with_volume(sink: dict[str, Any]) -> dict[str, Any]:
            try:
                _, out, _ = await self._run("wpctl", "get-volume", str(sink["pw_id"]), timeout=4)
                volume, muted = parse_wpctl_volume(out)
            except DeviceError:
                volume, muted = None, None
            return {**{k: v for k, v in sink.items() if k != "pw_id"}, "volume": volume, "muted": muted}

        devices = await asyncio.gather(*(with_volume(s) for s in data["sinks"]))
        devices.sort(key=lambda d: (not d["is_default"], d["name"].lower()))
        return {"supported": True, "devices": devices, "default_id": data["default_id"]}

    async def _pw_id(self, device_id: str) -> int:
        data = await self._audio_sinks()
        for sink in data["sinks"]:
            if sink["id"] == device_id:
                return int(sink["pw_id"])
        raise DeviceError("not_found", "Cette sortie audio n'est plus disponible.", 404)

    async def audio_set_default(self, device_id: str) -> None:
        pw_id = await self._pw_id(device_id)
        code, _, err = await self._run("wpctl", "set-default", str(pw_id), timeout=5)
        if code != 0:
            raise DeviceError("audio_failed", (err.strip() or "Changement de sortie refusé.")[:200], 502)
        self._emit("audio")

    async def audio_set_volume(self, device_id: str, volume: float | None, muted: bool | None) -> None:
        pw_id = await self._pw_id(device_id)
        if volume is not None:
            code, _, err = await self._run("wpctl", "set-volume", str(pw_id), f"{max(0.0, min(1.5, volume)):.2f}", timeout=5)
            if code != 0:
                raise DeviceError("audio_failed", (err.strip() or "Réglage du volume refusé.")[:200], 502)
        if muted is not None:
            code, _, err = await self._run("wpctl", "set-mute", str(pw_id), "1" if muted else "0", timeout=5)
            if code != 0:
                raise DeviceError("audio_failed", (err.strip() or "Réglage du son coupé refusé.")[:200], 502)
        self._emit("audio")

    # ------------------------------------------------------------------ Bluetooth (D-Bus)
    async def _ensure_bus(self) -> Any:
        if self._bus is not None:
            return self._bus
        async with self._bus_lock:
            if self._bus is not None:
                return self._bus
            try:
                from dbus_fast import BusType
                from dbus_fast.aio import MessageBus
            except ImportError as exc:
                raise DeviceError("dbus_missing", "Le module dbus-fast n'est pas installé.", 501) from exc
            try:
                bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            except Exception as exc:
                raise DeviceError("dbus_unavailable", "Le bus système D-Bus est inaccessible pour ce compte.", 502) from exc
            self._bus = bus
            await self._subscribe_bluez_signals(bus)
            await self._register_agent(bus)
            return bus

    async def _call(self, path: str, interface: str, member: str, signature: str = "", body: list[Any] | None = None, destination: str = _BLUEZ) -> list[Any]:
        from dbus_fast import Message, MessageType

        bus = await self._ensure_bus()
        try:
            reply = await asyncio.wait_for(
                bus.call(Message(destination=destination, path=path, interface=interface, member=member, signature=signature, body=body or [])),
                timeout=45,
            )
        except asyncio.TimeoutError as exc:
            raise DeviceError("timeout", "Le Bluetooth n'a pas répondu dans le délai imparti.", 504) from exc
        except Exception as exc:
            self._bus = None  # connexion perdue : sera rétablie au prochain appel
            raise DeviceError("dbus_unavailable", "Le service Bluetooth est inaccessible.", 502) from exc
        if reply.message_type == MessageType.ERROR:
            raise DeviceError(*_bluez_error(reply.error_name, reply.body))
        return list(reply.body)

    async def _bluez_objects(self) -> dict[str, dict[str, dict[str, Any]]]:
        body = await self._call("/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")
        return {
            path: {iface: {name: variant.value for name, variant in props.items()} for iface, props in ifaces.items()}
            for path, ifaces in body[0].items()
        }

    async def _bluetooth_snapshot(self) -> dict[str, Any]:
        return parse_bluez_objects(await self._bluez_objects())

    async def _subscribe_bluez_signals(self, bus: Any) -> None:
        from dbus_fast import Message, MessageType

        def on_message(msg: Any) -> None:
            if msg.message_type == MessageType.SIGNAL and (msg.path or "").startswith("/org/bluez") and msg.member in (
                "PropertiesChanged", "InterfacesAdded", "InterfacesRemoved"
            ):
                self._emit("bluetooth")

        bus.add_message_handler(on_message)
        try:
            await bus.call(
                Message(
                    destination="org.freedesktop.DBus", path="/org/freedesktop/DBus", interface="org.freedesktop.DBus",
                    member="AddMatch", signature="s", body=["type='signal',sender='org.bluez'"],
                )
            )
        except Exception as exc:  # sans signaux, l'écran se met à jour par interrogation périodique
            logger.debug("Abonnement aux signaux BlueZ impossible : %s", exc)

    async def _register_agent(self, bus: Any) -> None:
        try:
            from .linux_agent import make_agent

            self._agent = make_agent(self)
            bus.export(_AGENT_PATH, self._agent)
            await self._call("/org/bluez", "org.bluez.AgentManager1", "RegisterAgent", "os", [_AGENT_PATH, "KeyboardDisplay"])
            await self._call("/org/bluez", "org.bluez.AgentManager1", "RequestDefaultAgent", "o", [_AGENT_PATH])
        except DeviceError as exc:  # un autre agent (bureau GNOME/KDE) gère déjà l'appairage : on s'en contente
            logger.info("Agent d'appairage Bluetooth non enregistré : %s", exc.message)
            self._agent = None

    async def bluetooth_status(self) -> dict[str, Any]:
        reason = await self._probe_bluetooth()
        if reason:
            return unsupported(reason)
        snap = await self._bluetooth_snapshot()
        return {
            "supported": True,
            "powered": snap["powered"],
            "discovering": snap["discovering"],
            "adapter_name": snap["adapter_name"],
            "devices": [{k: v for k, v in d.items() if k != "path"} for d in snap["devices"]],
            "pending_pairing": self._pending,
            "pairing": self._pairing,
        }

    async def _adapter_path(self) -> str:
        snap = await self._bluetooth_snapshot()
        if not snap["adapter_path"]:
            raise DeviceError("no_adapter", "Aucun adaptateur Bluetooth détecté.", 501)
        return snap["adapter_path"]

    async def _set_adapter_prop(self, name: str, signature: str, value: Any) -> None:
        from dbus_fast import Variant

        path = await self._adapter_path()
        await self._call(path, "org.freedesktop.DBus.Properties", "Set", "ssv", ["org.bluez.Adapter1", name, Variant(signature, value)])

    async def bluetooth_set_power(self, on: bool) -> None:
        await self._set_adapter_prop("Powered", "b", on)
        self._emit("bluetooth")

    async def bluetooth_scan(self, on: bool) -> None:
        path = await self._adapter_path()
        snap = await self._bluetooth_snapshot()
        if on and not snap["powered"]:
            await self._set_adapter_prop("Powered", "b", True)
        if on == snap["discovering"]:
            return
        await self._call(path, "org.bluez.Adapter1", "StartDiscovery" if on else "StopDiscovery")
        self._emit("bluetooth")

    async def _device_path(self, address: str) -> str:
        if not is_valid_mac(address):
            raise DeviceError("bad_address", "Adresse Bluetooth invalide.", 400)
        return bluez_device_path(await self._adapter_path(), address)

    async def bluetooth_pair(self, address: str) -> None:
        path = await self._device_path(address)
        if self._pairing and self._pairing.get("state") == "pairing":
            raise DeviceError("busy", "Un appairage est déjà en cours.", 409)
        self._pairing = {"address": address.upper(), "state": "pairing", "error": None}
        self._emit("bluetooth")
        asyncio.create_task(self._pair_task(address.upper(), path))

    async def _pair_task(self, address: str, path: str) -> None:
        from dbus_fast import Variant

        try:
            await self._call(path, "org.bluez.Device1", "Pair")
            try:
                await self._call(path, "org.freedesktop.DBus.Properties", "Set", "ssv", ["org.bluez.Device1", "Trusted", Variant("b", True)])
                await self._call(path, "org.bluez.Device1", "Connect")
            except DeviceError as exc:  # appairé mais connexion refusée : l'utilisateur peut réessayer
                logger.info("Appairé, connexion non établie (%s) : %s", address, exc.message)
            self._pairing = {"address": address, "state": "paired", "error": None}
        except DeviceError as exc:
            self._pairing = {"address": address, "state": "failed", "error": exc.message}
        except Exception as exc:  # jamais d'exception non rattrapée dans une tâche
            logger.warning("Appairage Bluetooth interrompu : %s", exc)
            self._pairing = {"address": address, "state": "failed", "error": "Appairage interrompu."}
        finally:
            self._clear_pending()
            self._emit("bluetooth")

    async def bluetooth_respond_pairing(self, address: str, accept: bool) -> None:
        pending, future = self._pending, self._pending_future
        if not pending or future is None or future.done() or pending["address"].upper() != address.upper():
            raise DeviceError("no_pending", "Aucune demande d'appairage en attente pour cet appareil.", 409)
        future.set_result(bool(accept))

    async def bluetooth_connect(self, address: str) -> None:
        await self._call(await self._device_path(address), "org.bluez.Device1", "Connect")
        self._emit("bluetooth")

    async def bluetooth_disconnect(self, address: str) -> None:
        await self._call(await self._device_path(address), "org.bluez.Device1", "Disconnect")
        self._emit("bluetooth")

    async def bluetooth_forget(self, address: str) -> None:
        adapter = await self._adapter_path()
        await self._call(adapter, "org.bluez.Adapter1", "RemoveDevice", "o", [bluez_device_path(adapter, address) if is_valid_mac(address) else ""])
        self._emit("bluetooth")

    # --- appels de l'agent d'appairage ---
    def _set_pending(self, pending: dict[str, Any]) -> asyncio.Future[bool]:
        self._pending = pending
        self._pending_future = asyncio.get_running_loop().create_future()
        self._emit("bluetooth")
        return self._pending_future

    def _clear_pending(self) -> None:
        self._pending = None
        self._pending_future = None

    async def _agent_confirm(self, address: str, name: str, kind: str, passkey: str | None) -> bool:
        future = self._set_pending({"address": address, "name": name, "kind": kind, "passkey": passkey})
        try:
            return await asyncio.wait_for(future, timeout=_PAIR_PROMPT_TIMEOUT)
        except asyncio.TimeoutError:
            return False
        finally:
            self._clear_pending()
            self._emit("bluetooth")

    async def _device_label(self, path: str) -> tuple[str, str]:
        try:
            props = (await self._bluez_objects()).get(path, {}).get("org.bluez.Device1", {})
            address = str(props.get("Address") or path.rsplit("dev_", 1)[-1].replace("_", ":"))
            return address, str(props.get("Alias") or props.get("Name") or address)
        except DeviceError:
            address = path.rsplit("dev_", 1)[-1].replace("_", ":")
            return address, address

    # ------------------------------------------------------------------ Wi-Fi (nmcli)
    async def _nmcli(self, *args: str, timeout: float = 15.0, stdin: str | None = None) -> str:
        code, out, err = await self._run("nmcli", *args, timeout=timeout, stdin=stdin)
        if code != 0:
            raise DeviceError(*_nmcli_error(err or out))
        return out

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
        known_rows = parse_known_wifi(await self._nmcli("-t", "-f", "NAME,UUID,TYPE", "connection", "show", timeout=8))
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
        except DeviceError as exc:  # NetworkManager refuse les scans trop rapprochés : on relit simplement la liste
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
        known = {k["name"] for k in parse_known_wifi(await self._nmcli("-t", "-f", "NAME,UUID,TYPE", "connection", "show", timeout=8))}
        if ssid in known and not password:
            await self._nmcli("-w", "30", "connection", "up", "id", ssid, "ifname", device["device"], timeout=40)
        elif password:
            # --ask : le mot de passe est lu sur l'entrée standard, jamais placé en argument de commande.
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


def _bluez_error(error_name: str | None, body: list[Any]) -> tuple[str, str, int]:
    text = str(body[0]) if body else ""
    name = (error_name or "").rsplit(".", 1)[-1]
    table = {
        "AlreadyExists": ("already", "Cet appareil est déjà appairé.", 409),
        "AuthenticationFailed": ("pair_failed", "Échec de l'authentification (code refusé).", 400),
        "AuthenticationRejected": ("pair_rejected", "Appairage refusé.", 400),
        "AuthenticationCanceled": ("pair_cancelled", "Appairage annulé.", 400),
        "AuthenticationTimeout": ("timeout", "L'appareil n'a pas répondu à temps.", 504),
        "ConnectionAttemptFailed": ("connect_failed", "Connexion impossible : l'appareil est-il allumé et à portée ?", 502),
        "InProgress": ("busy", "Opération déjà en cours.", 409),
        "NotReady": ("not_ready", "Le Bluetooth n'est pas prêt (est-il activé ?).", 409),
        "NotAvailable": ("not_available", "Opération indisponible pour cet appareil.", 409),
        "DoesNotExist": ("not_found", "Appareil Bluetooth introuvable.", 404),
        "Failed": ("bt_failed", text[:200] or "Opération Bluetooth échouée.", 502),
        "NotAuthorized": ("not_authorized", "Le compte qui exécute Bobine n'a pas le droit d'utiliser le Bluetooth.", 403),
    }
    if "rfkill" in text.lower():
        return ("bluetooth_blocked", "Le Bluetooth est bloqué (interrupteur matériel ou rfkill).", 409)
    return table.get(name, ("bt_failed", text[:200] or "Opération Bluetooth échouée.", 502))
