"""Pilote Linux du stockage : commandes udisksctl/smartctl/busctl simulées par un exécuteur scripté (aucun root, aucun matériel)."""

import asyncio
import json
import os
import shutil

import pytest

os.environ.setdefault("BOBINE_DATABASE_URL", "sqlite:///data/test_database.db")

from app.devices.base import DeviceError  # noqa: E402
from app.storage.drivers import linux as linux_driver  # noqa: E402
from app.storage.drivers.linux import LinuxStorageDriver, classify_udisks_error  # noqa: E402
from app.storage.types import Volume  # noqa: E402

VOLUME = Volume(key="u-1", device="/dev/sdb1", name="sdb1", fs_uuid="1", label="L", fstype="exfat", size_bytes=1, mountpoint=None,
                transport="usb", disk="sdb", rotational=True, kind="hdd")


class Script:
    """Exécuteur scripté : `rules` = liste de (préfixe de commande, résultat ou exception) consommées dans l'ordre d'appel."""

    def __init__(self, *rules):
        self.rules = list(rules)
        self.calls: list[tuple[str, ...]] = []

    async def __call__(self, *args, **kwargs):
        self.calls.append(args)
        for index, (prefix, result) in enumerate(self.rules):
            if args[: len(prefix)] == prefix:
                if not (isinstance(result, list) and False):
                    pass
                outcome = result.pop(0) if isinstance(result, list) else result
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
        raise AssertionError(f"commande inattendue : {args}")


def run(coro):
    return asyncio.run(coro)


def driver(*rules, **kw):
    script = Script(*rules)
    return LinuxStorageDriver(runner=script, **kw), script


def test_mount_parses_the_mount_point_and_passes_options_without_a_shell():
    d, script = driver((("udisksctl", "mount"), (0, "Mounted /dev/sdb1 at /run/media/u/MON DISQUE.\n", "")))
    assert run(d.mount(VOLUME, ["ro", "noatime"])) == "/run/media/u/MON DISQUE"
    assert script.calls[0] == ("udisksctl", "mount", "-b", "/dev/sdb1", "-o", "ro,noatime", "--no-user-interaction")


def test_already_mounted_returns_the_existing_mount_point():
    err = "Error mounting /dev/sdb1: GDBus.Error:org.freedesktop.UDisks2.Error.AlreadyMounted: Device /dev/sdb1 is already mounted at `/run/media/u/X'.\n"
    d, _ = driver((("udisksctl", "mount"), (1, "", err)))
    assert run(d.mount(VOLUME, ["ro"])) == "/run/media/u/X"


@pytest.mark.parametrize("message,code,status", [
    ("GDBus.Error:org.freedesktop.UDisks2.Error.OptionNotPermitted: Mount option `discard' is not allowed", "option_not_permitted", 400),
    ("GDBus.Error:org.freedesktop.UDisks2.Error.NotAuthorizedCanObtain: Not authorized to perform operation", "not_authorized", 403),
    ("target is busy", "busy", 409),
    ("mount: wrong fs type, bad option, bad superblock; NTFS is inconsistent", "dirty", 409),
    ("The disk contains an unclean file system (0, 0). Metadata kept in Windows cache, refused to mount. hibernated", "dirty", 409),
    ("Object /org/freedesktop/UDisks2/block_devices/sdb1 is not a mountable filesystem.", "unsupported_fs", 400),
    ("Error: no such object path", "device_removed", 404),
    ("???", "mount_failed", 502),
])
def test_udisks_errors_are_classified(message, code, status):
    assert classify_udisks_error(message)[:2] == (code, status)
    d, _ = driver((("udisksctl", "mount"), (1, "", message)))
    with pytest.raises(DeviceError) as exc:
        run(d.mount(VOLUME, ["ro"]))
    assert exc.value.code == code and exc.value.status == status


def test_unmount_is_idempotent_and_reports_busy():
    d, _ = driver((("udisksctl", "unmount"), (1, "", "GDBus.Error:org.freedesktop.UDisks2.Error.NotMounted: Device is not mounted")))
    run(d.unmount(VOLUME))
    d, _ = driver((("udisksctl", "unmount"), (1, "", "Error unmounting: target is busy")))
    with pytest.raises(DeviceError) as exc:
        run(d.unmount(VOLUME))
    assert exc.value.code == "busy"


def test_power_off_targets_the_parent_disk_and_loop_images_are_released():
    d, script = driver((("udisksctl", "power-off"), (0, "", "")))
    assert run(d.power_off(VOLUME)) is True and script.calls[0][3] == "/dev/sdb"
    loop = Volume(**{**VOLUME.__dict__, "dev_type": "loop", "device": "/dev/loop9", "disk": "loop9"})
    d, script = driver((("udisksctl", "loop-delete"), (0, "", "")))
    assert run(d.power_off(loop)) is True and script.calls[0][:3] == ("udisksctl", "loop-delete", "-b")
    sd = Volume(**{**VOLUME.__dict__, "sd_card": True, "kind": "sd"})
    d, script = driver()
    assert run(d.power_off(sd)) is False and script.calls == []  # carte SD : rien à éteindre


def lsblk_json(extra=()):
    return json.dumps({"blockdevices": [
        {"name": "sda", "path": "/dev/sda", "type": "disk", "rm": True, "hotplug": True, "tran": "usb", "rota": False, "size": 10, "children": [
            {"name": "sda1", "path": "/dev/sda1", "type": "part", "fstype": "exfat", "uuid": "AB12-CD34", "label": "CLE", "size": 9, "mountpoints": [None], "ro": False}]},
        {"name": "nvme0n1", "path": "/dev/nvme0n1", "type": "disk", "rm": False, "hotplug": False, "size": 100, "children": [
            {"name": "nvme0n1p2", "path": "/dev/nvme0n1p2", "type": "part", "fstype": "ext4", "mountpoints": ["/"], "size": 90}]},
        *extra]})


def test_inventory_runs_lsblk_once_reads_mountinfo_and_excludes_system(tmp_path):
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text("1 0 0:1 / / rw - ext4 /dev/nvme0n1p2 rw\n")
    (tmp_path / "block" / "sda" / "device").mkdir(parents=True)
    d, script = driver((("lsblk",), (0, lsblk_json(), "")), mountinfo_path=str(mountinfo), sys_block=str(tmp_path / "block"))
    inv = run(d.inventory(["/srv/bobine/data"]))
    assert [v.name for v in inv.volumes] == ["sda1"] and len(script.calls) == 1
    assert script.calls[0][:3] == ("lsblk", "-J", "-b") and "MOUNTPOINTS" in script.calls[0][4] and "PKNAME" in script.calls[0][4]


def test_inventory_retries_with_fewer_columns_on_old_util_linux():
    d, script = driver((("lsblk",), [(1, "", "lsblk: unknown column: DISC-GRAN"), (0, lsblk_json(), "")]))
    assert [v.name for v in run(d.inventory([])).volumes] == ["sda1"] and "DISC-GRAN" not in script.calls[1][4]


def test_inventory_errors_are_structured():
    d, _ = driver((("lsblk",), (1, "", "boom")))
    with pytest.raises(DeviceError) as exc:
        run(d.inventory([]))
    assert exc.value.code == "inventory_failed" and exc.value.status == 502
    d, _ = driver((("lsblk",), (0, "pas du json", "")))
    with pytest.raises(DeviceError):
        run(d.inventory([]))


def test_sd_card_detection_reads_sysfs(tmp_path):
    (tmp_path / "mmcblk0" / "device").mkdir(parents=True)
    (tmp_path / "mmcblk0" / "device" / "type").write_text("SD\n")
    (tmp_path / "mmcblk1" / "device").mkdir(parents=True)
    (tmp_path / "mmcblk1" / "device" / "type").write_text("MMC\n")
    d, _ = driver(sys_block=str(tmp_path))
    assert d._is_sd("mmcblk0") is True and d._is_sd("mmcblk1") is False and d._is_sd("sdz") is False


def test_smart_missing_tool_permission_and_usb_bridge_retry(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    d, _ = driver()
    assert run(d.smart(VOLUME))["reason"] == "tool_missing"
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/sbin/{name}")
    ata = {"smartctl": {"exit_status": 0}, "smart_support": {"available": True}, "smart_status": {"passed": True}, "ata_smart_attributes": {"table": []}, "temperature": {"current": 30}}
    no_bridge = {"smartctl": {"exit_status": 4, "messages": [{"string": "Unknown USB bridge"}]}}
    d, script = driver((("smartctl",), [(4, json.dumps(no_bridge), ""), (0, json.dumps(ata), "")]))
    report = run(d.smart(VOLUME))
    assert report["available"] and report["temperature_c"] == 30
    assert script.calls[1] == ("smartctl", "-j", "-a", "-d", "sat", "/dev/sdb")  # pont USB-SATA retenté
    denied = {"smartctl": {"exit_status": 2, "messages": [{"string": "Permission denied"}]}}
    d, _ = driver((("smartctl",), (2, json.dumps(denied), "")))
    assert run(d.smart(VOLUME))["reason"] == "permission"
    d, _ = driver((("smartctl",), (2, "", "Smartctl open device: /dev/sdb failed: Permission denied")))
    assert run(d.smart(VOLUME))["reason"] == "permission"


def test_standby_uses_udisks_without_privileges_and_reports_failures(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    d, script = driver(
        (("busctl", "--system", "get-property"), (0, 'o "/org/freedesktop/UDisks2/drives/WD_Elements"\n', "")),
        (("busctl", "--system", "call"), (0, "", "")),
    )
    assert run(d.standby(VOLUME)) == "udisks"
    assert script.calls[1][4] == "/org/freedesktop/UDisks2/drives/WD_Elements" and script.calls[1][6] == "PmStandby"
    d, _ = driver(
        (("busctl", "--system", "get-property"), (0, 'o "/org/freedesktop/UDisks2/drives/X"\n', "")),
        (("busctl", "--system", "call"), (1, "", "Not authorized to perform operation")),
    )
    with pytest.raises(DeviceError) as exc:
        run(d.standby(VOLUME))
    assert exc.value.code == "standby_failed" and "Not authorized" in exc.value.message


def test_trim_needs_root_and_a_writable_mount(monkeypatch):
    mounted_rw = Volume(**{**VOLUME.__dict__, "mountpoint": "/run/media/u/L", "mounts": ("/run/media/u/L",), "mount_options": ("rw",)})
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    d, _ = driver()
    with pytest.raises(DeviceError) as exc:
        run(d.trim(mounted_rw))
    assert exc.value.code == "needs_root"
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    read_only = Volume(**{**mounted_rw.__dict__, "mount_options": ("ro",)})
    with pytest.raises(DeviceError) as exc:
        run(d.trim(read_only))
    assert exc.value.code == "read_only"
    d, script = driver((("fstrim",), (0, "/run/media/u/L: 1 GiB trimmed", "")))
    assert "trimmed" in run(d.trim(mounted_rw)) and script.calls[0] == ("fstrim", "-v", "/run/media/u/L")


def test_capabilities_are_honest_when_tools_are_missing(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    d, _ = driver()
    caps = run(d.capabilities())
    assert caps["inventory"]["supported"] is False and "lsblk" in caps["inventory"]["reason"]
    assert caps["mount"]["supported"] is False and "udisks2" in caps["mount"]["reason"]
    assert caps["smart"]["supported"] is False and "smartmontools" in caps["smart"]["reason"]
    assert caps["portable"]["supported"] is False and "gvfs-backends" in caps["portable"]["reason"]
    assert caps["trim"]["supported"] is False and caps["standby"]["supported"] is False


def test_portable_without_gvfs_gives_install_help_not_an_error(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    d, _ = driver()
    monkeypatch.setattr(d, "_usb_candidates", lambda: [__import__("app.storage.portable", fromlist=["x"]).PortableDevice("p-1", "Google Pixel", "mtp", None, "detected", "001", "007")])
    status = run(d.portable_status())
    assert status["supported"] is False and status["reason"] == "missing_tool" and "gvfs-backends" in status["install"]
    assert status["devices"][0]["state"] == "missing_tool" and status["devices"][0]["install"]
    with pytest.raises(DeviceError) as exc:
        run(d.portable_mount("p-1"))
    assert exc.value.code == "missing_tool" and exc.value.status == 501


def test_portable_mount_reports_phone_states(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    gio_list = "Volume(0): Pixel 7\n  ids:\n   unix-device: '/dev/bus/usb/001/007'\n  activation_root=mtp://Google_Pixel_7_ABC/\n"
    d, script = driver((("gio", "mount", "-li"), (0, gio_list, "")), (("gio", "mount", "mtp://Google_Pixel_7_ABC/"), (1, "", "Error mounting location: Unable to open MTP device")))
    device_id = run(d.portable_status())["devices"][0]["id"]
    with pytest.raises(DeviceError) as exc:
        run(d.portable_mount(device_id))
    assert exc.value.code == "not_ready" and "Transfert de fichiers" in exc.value.message
    gvfs = tmp_path / "gvfs" / "mtp:host=Google_Pixel_7_ABC"
    gvfs.mkdir(parents=True)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    d, _ = driver((("gio", "mount", "-li"), (0, gio_list, "")), (("gio", "mount", "mtp://Google_Pixel_7_ABC/"), (0, "", "")))
    assert run(d.portable_mount(device_id))["root"] == str(gvfs)
