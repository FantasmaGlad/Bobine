"""Appareils portables (téléphones, tablettes, appareils photo) via GVFS : MTP, PTP, AFC (iPhone/iPad).

Pourquoi GVFS (`gio mount`) : udev/udisks ne gèrent pas MTP ; GVFS est déjà installé sur tout Linux de
bureau, fonctionne sans droits d'administrateur et expose l'appareil comme un dossier FUSE lisible
(`/run/user/UID/gvfs/mtp:host=…`). Aucune dépendance Python ajoutée. Sans GVFS : état `missing_tool`
et aide d'installation, jamais un échec.

Règles propres aux appareils portables :

* **lecture seule** : jamais d'écriture, jamais de suppression ;
* **import oui, extension de stockage non** : MTP n'est pas fiable pour le flux (pas d'accès aléatoire
  garanti, coupures au verrouillage de l'écran) ; l'interface le dit et propose d'importer ;
* états explicites : `missing_tool`, `detected` (vu sur le port USB, GVFS ne le propose pas encore :
  verrouillé / mode transfert non activé), `ready`, `mounted`, `busy`, `locked`, `needs_approval`,
  `not_ready`.

Aucun appareil portable n'a pu être branché pendant le développement : les analyseurs sont testés sur
des sorties types, **non validés sur matériel**."""

from __future__ import annotations

import hashlib
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any

SCHEMES = ("mtp", "gphoto2", "afc")
INSTALL_HELP = {
    "mtp": "sudo apt install gvfs-backends gvfs-fuse",
    "afc": "sudo apt install gvfs-backends gvfs-fuse libimobiledevice-utils usbmuxd",
    "gphoto2": "sudo apt install gvfs-backends gvfs-fuse",
}
APPLE_VENDOR = "05ac"
HINT_MESSAGES = {
    "unlock_device": "L'appareil est verrouillé : déverrouillez-le puis réessayez.",
    "accept_on_device": "Acceptez l'autorisation affichée sur l'appareil (« Autoriser l'accès aux données » ou « Faire confiance à cet ordinateur »), puis réessayez.",
    "close_other_app": "L'appareil est déjà utilisé par un autre programme (gestionnaire de fichiers, Android File Transfer…) : fermez-le puis réessayez.",
    "unlock_and_transfer_mode": "Déverrouillez l'appareil, choisissez « Transfert de fichiers » (MTP) dans la notification USB et acceptez l'autorisation affichée, puis réessayez.",
}


@dataclass
class PortableDevice:
    id: str
    name: str
    scheme: str
    uri: str | None
    state: str
    bus: str | None = None
    dev: str | None = None
    hint: str | None = None  # code de conseil traduit par l'interface
    root: str | None = None  # dossier FUSE quand monté
    vendor_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "scheme": self.scheme,
            "state": self.state,
            "hint": self.hint,
            "read_only": True,
            "direct_playback": False,  # MTP/AFC : import uniquement
            "install": INSTALL_HELP.get(self.scheme) if self.state == "missing_tool" else None,
        }


def device_id(seed: str) -> str:
    return "p-" + hashlib.sha1(seed.encode()).hexdigest()[:12]


_BUS_DEV = re.compile(r"/dev/bus/usb/(\d+)/(\d+)")
_BRACKET = re.compile(r"\[usb:(\d+),(\d+)\]")


def split_uri(uri: str) -> tuple[str, str]:
    """(schéma, hôte) d'une URI GVFS ; `urlsplit` refuse les hôtes MTP entre crochets (`mtp://[usb:001,008]/`)."""
    match = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*)://([^/]*)", uri)
    return (match.group(1).lower(), match.group(2)) if match else ("", "")


def parse_gio_mounts(text: str) -> list[PortableDevice]:
    """Analyse `gio mount -li` : volumes et montages dont l'URI relève de MTP, PTP ou AFC (les autres sont ignorés)."""
    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        match = re.match(r"^(Drive|Volume|Mount)\((\d+)\):\s*(.*)$", line.strip())
        if match and not raw.startswith("    "):
            kind, _, rest = match.groups()
            current = {"kind": kind, "name": rest, "lines": []}
            if kind == "Mount" and " -> " in rest:
                name, uri = rest.rsplit(" -> ", 1)
                current["name"], current["uri"] = name.strip(), uri.strip()
            blocks.append(current)
        elif current is not None:
            current["lines"].append(line.strip())

    devices: dict[str, PortableDevice] = {}
    for block in blocks:
        if block["kind"] == "Drive":
            continue
        uri = block.get("uri")
        bus = dev = None
        for line in block["lines"]:
            if line.startswith("activation_root=") and not uri:
                uri = line.split("=", 1)[1].strip()
            m = re.search(r"unix-device:\s*'([^']+)'", line)
            if m and (mm := _BUS_DEV.search(m.group(1))):
                bus, dev = mm.group(1), mm.group(2)
            if line.startswith("default_location=") and block["kind"] == "Mount":
                uri = uri or line.split("=", 1)[1].strip()
        if not uri:
            continue
        scheme = uri.split(":", 1)[0].lower()
        if scheme not in SCHEMES:
            continue
        if not bus and (mb := _BRACKET.search(uri)):
            bus, dev = mb.group(1), mb.group(2)
        root_uri = scheme + "://" + split_uri(uri)[1] + "/"
        existing = devices.get(root_uri)
        mounted = block["kind"] == "Mount"
        name = block["name"] or root_uri
        if existing is None:
            devices[root_uri] = PortableDevice(device_id(root_uri), name, scheme, root_uri, "mounted" if mounted else "ready", bus, dev)
        elif mounted:
            existing.state = "mounted"
            existing.name = name or existing.name
    return list(devices.values())


def fuse_root_for(uri: str, gvfs_dir: str) -> str | None:
    """Dossier FUSE d'un appareil monté : `mtp://HOTE/` → `<gvfs>/mtp:host=HOTE` (nom décodé ou non)."""
    scheme, netloc = split_uri(uri)
    host = urllib.parse.unquote(netloc)
    try:
        names = os.listdir(gvfs_dir)
    except OSError:
        return None
    for name in names:
        if not name.startswith(scheme + ":"):
            continue
        entry_host = urllib.parse.unquote(name.split("host=", 1)[1]) if "host=" in name else ""
        if entry_host == host:
            return os.path.join(gvfs_dir, name)
    return None


def classify_mount_error(stderr: str) -> tuple[str, str]:
    """(état, code de conseil) d'après le message d'échec de `gio mount`."""
    low = stderr.lower()
    if "locked" in low or "passcode" in low or "password protected" in low:
        return "locked", "unlock_device"
    if "trust" in low or "pair" in low or "lockdownd" in low or "not authorized" in low or "authorization" in low:
        return "needs_approval", "accept_on_device"
    if "busy" in low or "already" in low or "claimed" in low or "in use" in low:
        return "busy", "close_other_app"
    if "unable to open mtp" in low or "no such" in low or "not supported" in low or "could not" in low:
        return "not_ready", "unlock_and_transfer_mode"
    return "not_ready", "unlock_and_transfer_mode"


def parse_sysfs_usb(devices: list[dict[str, Any]]) -> list[PortableDevice]:
    """Appareils USB qui ressemblent à un téléphone/tablette/appareil photo (interfaces PTP/MTP ou usbmux Apple).

    Chaque dict : `busnum`, `devnum`, `idVendor`, `idProduct`, `product`, `manufacturer`, `interfaces` (liste de
    `{class, subclass, protocol, name}`). Sert à signaler un appareil que GVFS ne propose pas encore."""
    found: list[PortableDevice] = []
    for dev in devices:
        interfaces = dev.get("interfaces") or []
        vendor = str(dev.get("idVendor") or "").lower()
        scheme = None
        for itf in interfaces:
            klass = str(itf.get("class") or "").lower()
            name = str(itf.get("name") or "").lower()
            if klass == "06":  # Still Image (PTP)
                scheme = "mtp"
            elif klass == "ff" and "mtp" in name:
                scheme = "mtp"
            elif vendor == APPLE_VENDOR and klass == "ff" and str(itf.get("subclass") or "").lower() == "fe":
                scheme = "afc"
        if scheme is None:
            continue
        label = " ".join(p for p in (str(dev.get("manufacturer") or "").strip(), str(dev.get("product") or "").strip()) if p) or "Appareil USB"
        bus, num = str(dev.get("busnum") or "").zfill(3), str(dev.get("devnum") or "").zfill(3)
        found.append(PortableDevice(device_id(f"usb:{bus}:{num}"), label, scheme, None, "detected", bus, num, "unlock_and_transfer_mode", vendor_id=vendor))
    return found


def merge(gvfs: list[PortableDevice], usb: list[PortableDevice]) -> list[PortableDevice]:
    """Fusionne GVFS (précis) et sysfs (présence) : un appareil vu sur le port USB mais absent de GVFS reste `detected`."""
    known = {(d.bus and d.bus.lstrip("0"), d.dev and d.dev.lstrip("0")) for d in gvfs if d.bus}
    merged = list(gvfs)
    for dev in usb:
        if (dev.bus.lstrip("0"), dev.dev.lstrip("0")) in known:  # type: ignore[union-attr]
            continue
        merged.append(dev)
    return merged
