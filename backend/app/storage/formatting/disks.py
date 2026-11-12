"""Analyse de `lsblk -J -b` en disques entiers avec leurs partitions (logique pure, testée sans matériel)."""

from __future__ import annotations

import json
from typing import Any, Callable

from app.storage.lsblk import as_flag, as_int, as_text, classify_kind
from .model import DiskInfo, PartInfo

DISK_COLUMNS = "NAME,PATH,UUID,LABEL,FSTYPE,SIZE,RM,HOTPLUG,TRAN,MOUNTPOINTS,MODEL,SERIAL,TYPE,RO,ROTA,VENDOR,PARTN,PTTYPE,START"
DISK_COLUMNS_FALLBACK = "NAME,PATH,UUID,LABEL,FSTYPE,SIZE,RM,HOTPLUG,TRAN,MOUNTPOINTS,MODEL,SERIAL,TYPE,RO,ROTA"


def _mountpoints(node: dict[str, Any]) -> tuple[str, ...]:
    raw = node.get("mountpoints")
    if raw is None and node.get("mountpoint"):
        raw = [node.get("mountpoint")]
    return tuple(m for m in (raw or []) if m)


def _part(node: dict[str, Any], whole: bool) -> PartInfo:
    start = node.get("start")
    return PartInfo(
        name=str(node.get("name") or ""),
        path=str(node.get("path") or f"/dev/{node.get('name')}"),
        fstype=as_text(node.get("fstype")),
        label=as_text(node.get("label")),
        uuid=as_text(node.get("uuid")),
        size_bytes=as_int(node.get("size")),
        mountpoints=_mountpoints(node),
        partn=as_text(node.get("partn")),
        read_only=as_flag(node.get("ro")),
        start_sectors=as_int(start) if start not in (None, "") else None,
        whole_disk=whole,
    )


def _flatten(node: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for child in node.get("children") or []:
        out.append(child)
        out.extend(_flatten(child))
    return out


def parse_disks(data: str | dict[str, Any], *, is_sd_card: Callable[[str], bool] | None = None) -> list[DiskInfo]:
    """Un `DiskInfo` par disque ou image disque de premier niveau (lecteurs optiques et disques en mémoire ignorés)."""
    payload = json.loads(data) if isinstance(data, str) else data
    sd_probe = is_sd_card or (lambda _name: False)
    disks: list[DiskInfo] = []
    for top in payload.get("blockdevices", []):
        top_type = str(top.get("type") or "disk")
        if top_type in ("rom", "ram"):
            continue
        name = str(top.get("name") or "")
        children = _flatten(top)
        parts = [_part(c, False) for c in children if str(c.get("type") or "part") in ("part", "crypt", "lvm", "md", "raid1", "raid0", "raid5", "dm")]
        if not parts:
            parts = [_part(c, False) for c in children]
        if top.get("fstype"):
            parts.insert(0, _part(top, True))
        size = as_int(top.get("size"))
        rotational = None if top.get("rota") is None else as_flag(top.get("rota"))
        transport = as_text(top.get("tran"))
        sd_card = sd_probe(name)
        is_loop = top_type == "loop"
        disks.append(DiskInfo(
            name=name,
            path=str(top.get("path") or f"/dev/{name}"),
            dev_type="loop" if is_loop else "disk",
            size_bytes=size,
            vendor=as_text(top.get("vendor")),
            model=as_text(top.get("model")),
            serial=as_text(top.get("serial")),
            transport=transport,
            removable=as_flag(top.get("rm")),
            hotplug=as_flag(top.get("hotplug")),
            read_only=as_flag(top.get("ro")),
            rotational=rotational,
            ptable=as_text(top.get("pttype")),
            sd_card=sd_card,
            kind=classify_kind(transport=transport, rotational=rotational, sd_card=sd_card, name=name, size=size, dev_type="loop" if is_loop else "disk"),
            partitions=tuple(parts),
        ))
    return disks
