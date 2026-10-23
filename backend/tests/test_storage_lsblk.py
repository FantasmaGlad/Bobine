"""Stockage externe : analyse de lsblk, règles d'exclusion strictes, options de montage, identité des volumes.

Logique pure : aucune dépendance au matériel, au bus système ni à la base."""

import json

from app.storage.lsblk import (
    DATA_FILESYSTEMS,
    classify_kind,
    duplicate_uuids,
    is_system_mount,
    overlaps_protected,
    parse_lsblk,
    parse_mountinfo,
)
from app.storage.types import make_key, volume_public


def node(name, **kw):
    base = {"name": name, "path": f"/dev/{name}", "uuid": None, "label": None, "fstype": None, "size": 8 * 10**9,
            "rm": False, "hotplug": False, "tran": None, "mountpoints": [None], "model": None, "serial": None,
            "type": "part", "ro": False, "rota": False, "pkname": None, "vendor": None, "disc-gran": 0, "partn": None}
    base.update(kw)
    return base


SYSTEM_DISK = node("nvme0n1", type="disk", model="SAMSUNG", children=[
    node("nvme0n1p1", fstype="vfat", mountpoints=["/boot/efi"], uuid="AAAA-0001"),
    node("nvme0n1p2", fstype="ext4", mountpoints=["/"], uuid="11111111-1111-1111-1111-111111111111"),
])
USB_STICK = node("sda", type="disk", rm=True, hotplug=True, tran="usb", model="Cruzer", vendor="SanDisk", serial="SN1", rota=False,
                 size=64 * 10**9, children=[
    node("sda1", fstype="exfat", label="COURS", uuid="7FDB-F2EC", mountpoints=["/run/media/u/COURS"], partn=1, size=63 * 10**9),
])
USB_HDD = node("sdb", type="disk", hotplug=True, tran="usb", model="Elements", vendor="WD", serial="SN2", rota=True,
               size=2 * 10**12, children=[
    node("sdb1", fstype="ntfs", label="DISQUE", uuid="0123456789ABCDEF", mountpoints=[None], partn=1),
    node("sdb2", fstype="ext4", label="LINUX", uuid="22222222-2222-2222-2222-222222222222", mountpoints=["/run/media/u/LINUX"], partn=2),
])
SD_CARD = node("mmcblk0", type="disk", model=None, rota=False, size=32 * 10**9, children=[
    node("mmcblk0p1", fstype="vfat", label="SD", uuid="1234-5678", mountpoints=[None], partn=1),
])
EMMC = node("mmcblk1", type="disk", rota=False, children=[node("mmcblk1p1", fstype="ext4", uuid="33333333-3333-3333-3333-333333333333", mountpoints=[None])])
SNAP_LOOP = node("loop0", type="loop", fstype="squashfs", mountpoints=["/snap/core/1"], ro=True)
SNAP_LOOP2 = node("loop1", type="loop", fstype="squashfs", mountpoints=[None], ro=True)
IMAGE_LOOP = node("loop7", type="loop", fstype="ext4", uuid="44444444-4444-4444-4444-444444444444", label="IMG", mountpoints=["/run/media/u/IMG"])
FIXED_SATA = node("sdc", type="disk", tran="sata", rota=True, children=[node("sdc1", fstype="ext4", uuid="55555555-5555-5555-5555-555555555555", mountpoints=[None])])
SWAP = node("zram0", type="disk", fstype="swap", mountpoints=["[SWAP]"])
LUKS_USB = node("sdd", type="disk", rm=True, hotplug=True, tran="usb", children=[node("sdd1", fstype="crypto_LUKS", uuid="66666666-6666-6666-6666-666666666666")])
ROM = node("sr0", type="rom", rm=True, fstype="iso9660")


def listing(*disks):
    return {"blockdevices": list(disks)}


def volumes_of(inv):
    return {v.name: v for v in inv.volumes}


def test_usb_stick_is_listed_with_identity_and_kind():
    inv = parse_lsblk(listing(USB_STICK))
    v = volumes_of(inv)["sda1"]
    assert v.fs_uuid == "7FDB-F2EC" and v.label == "COURS" and v.fstype == "exfat"
    assert v.kind == "usb" and v.transport == "usb" and v.mounted and v.mountpoint == "/run/media/u/COURS"
    assert v.key == "u-7fdb-f2ec" and v.disk == "sda" and v.display_name == "COURS"


def test_system_disk_is_never_listed():
    inv = parse_lsblk(listing(SYSTEM_DISK, USB_STICK))
    assert set(volumes_of(inv)) == {"sda1"}
    assert {e.reason for e in inv.excluded} == {"system"}


def test_disk_with_any_system_mount_is_system_even_if_removable():
    """Un disque « USB » qui porte / (installation sur clé) ou /home n'est jamais proposé."""
    booted_usb = node("sde", type="disk", rm=True, hotplug=True, tran="usb", children=[
        node("sde1", fstype="ext4", mountpoints=["/"], uuid="77777777-7777-7777-7777-777777777777"),
        node("sde2", fstype="ext4", mountpoints=[None], uuid="88888888-8888-8888-8888-888888888888"),
    ])
    inv = parse_lsblk(listing(booted_usb))
    assert inv.volumes == []
    assert is_system_mount("/") and is_system_mount("/boot/efi") and is_system_mount("/snap/core/1") and not is_system_mount("/run/media/u/USB")


def test_internal_fixed_disks_are_hidden():
    inv = parse_lsblk(listing(FIXED_SATA))
    assert inv.volumes == [] and [e.reason for e in inv.excluded] == ["internal"]


def test_swap_and_optical_are_ignored():
    inv = parse_lsblk(listing(SWAP, ROM))
    assert inv.volumes == []


def test_sd_card_detected_only_when_sysfs_says_sd():
    with_sd = parse_lsblk(listing(SD_CARD, EMMC), is_sd_card=lambda name: name == "mmcblk0")
    assert set(volumes_of(with_sd)) == {"mmcblk0p1"}
    assert volumes_of(with_sd)["mmcblk0p1"].kind == "sd"
    without = parse_lsblk(listing(SD_CARD, EMMC))
    assert without.volumes == []  # eMMC interne et carte non identifiée : écartées par prudence


def test_loop_images_snap_squashfs_excluded_data_image_listed():
    inv = parse_lsblk(listing(SNAP_LOOP, SNAP_LOOP2, IMAGE_LOOP))
    assert set(volumes_of(inv)) == {"loop7"} and volumes_of(inv)["loop7"].kind == "image"
    assert parse_lsblk(listing(IMAGE_LOOP), include_images=False).volumes == []


def test_volume_holding_bobine_data_is_excluded():
    inv = parse_lsblk(listing(USB_STICK), protected_paths=["/run/media/u/COURS/bobine/data/videos"])
    assert inv.volumes == [] and inv.excluded[0].reason == "bobine_data"
    # Monté DANS un dossier de données de Bobine : écarté aussi.
    inside = node("sdf", type="disk", rm=True, hotplug=True, tran="usb", children=[
        node("sdf1", fstype="exfat", uuid="9999-9999", mountpoints=["/srv/bobine/data/videos/usb"])])
    assert parse_lsblk(listing(inside), protected_paths=["/srv/bobine/data/videos"]).volumes == []
    assert overlaps_protected("/mnt/x", ["/mnt/x"]) and not overlaps_protected("/mnt/x", ["/mnt/xy/data"])


def test_luks_is_reported_but_not_usable():
    inv = parse_lsblk(listing(LUKS_USB))
    assert inv.volumes == [] and len(inv.encrypted) == 1 and inv.excluded[0].reason == "encrypted"


def test_partitions_of_a_hdd_keep_rotational_and_distinct_keys():
    inv = parse_lsblk(listing(USB_HDD))
    vols = volumes_of(inv)
    assert vols["sdb1"].kind == "hdd" and vols["sdb1"].rotational is True and not vols["sdb1"].mounted
    assert vols["sdb2"].mounted and vols["sdb1"].key != vols["sdb2"].key


def test_old_util_linux_string_booleans_and_singular_mountpoint():
    old = {"blockdevices": [{
        "name": "sdg", "path": "/dev/sdg", "type": "disk", "rm": "1", "hotplug": "1", "ro": "0", "tran": "usb", "size": "1000000",
        "children": [{"name": "sdg1", "path": "/dev/sdg1", "type": "part", "fstype": "vfat", "uuid": "ABCD-1234", "size": "900000",
                      "mountpoint": "/media/x", "ro": "1"}]}]}
    inv = parse_lsblk(old)
    v = inv.volumes[0]
    assert v.removable and v.mountpoint == "/media/x" and v.read_only_device and v.size_bytes == 900000 and v.mounted_read_only is True


def test_mount_options_come_from_mountinfo_not_lsblk():
    mountinfo = (
        "50 1 0:45 / /run/media/u/COURS rw,nosuid,nodev,noatime shared:1 - exfat /dev/sda1 rw,uid=1000,errors=remount-ro\n"
        "51 1 0:46 / /run/media/u/with\\040space ro,nodev - ext4 /dev/sdb1 ro\n"
    )
    entries = parse_mountinfo(mountinfo)
    assert entries[0].mountpoint == "/run/media/u/COURS" and "noatime" in entries[0].options and "rw" in entries[0].options
    assert entries[1].mountpoint == "/run/media/u/with space"
    inv = parse_lsblk(listing(USB_STICK), mountinfo=entries)
    v = inv.volumes[0]
    assert "noatime" in v.mount_options and v.mounted_read_only is False


def test_keys_are_uuid_based_and_never_mount_point_based():
    assert make_key("7FDB-F2EC", None, None, None, 1) == "u-7fdb-f2ec"
    assert make_key("a/b c", None, None, None, 1) == "u-a_b_c"
    k = make_key(None, "SN", "Model", "1", 100)
    assert k.startswith("d-") and k == make_key(None, "SN", "Model", "1", 100) != make_key(None, "SN", "Model", "2", 100)


def test_public_view_never_leaks_device_paths_or_serials():
    inv = parse_lsblk(listing(USB_STICK))
    dumped = json.dumps(volume_public(inv.volumes[0]))
    assert "/dev/" not in dumped and "SN1" not in dumped and "/run/media" not in dumped


def test_duplicate_uuids_are_detected():
    twin = node("sdh", type="disk", rm=True, hotplug=True, tran="usb", children=[node("sdh1", fstype="exfat", uuid="7fdb-f2ec", mountpoints=[None])])
    inv = parse_lsblk(listing(USB_STICK, twin))
    assert duplicate_uuids(inv.volumes) == {"7fdb-f2ec"}


def test_kind_classification():
    assert classify_kind(transport="usb", rotational=True, sd_card=False, name="sdb", size=10**12, dev_type="disk") == "hdd"
    assert classify_kind(transport="usb", rotational=False, sd_card=False, name="sda", size=32 * 10**9, dev_type="disk") == "usb"
    assert classify_kind(transport="usb", rotational=False, sd_card=False, name="sda", size=10**12, dev_type="disk") == "ssd"
    assert classify_kind(transport=None, rotational=False, sd_card=True, name="mmcblk0", size=1, dev_type="disk") == "sd"
    assert classify_kind(transport=None, rotational=False, sd_card=False, name="loop3", size=1, dev_type="loop") == "image"
    assert {"exfat", "vfat", "ntfs", "ext4"} <= DATA_FILESYSTEMS


def test_cloned_uuids_get_distinct_keys():
    twin = node("sdh", type="disk", rm=True, hotplug=True, tran="usb", children=[node("sdh1", fstype="exfat", uuid="7fdb-f2ec", mountpoints=[None])])
    inv = parse_lsblk(listing(USB_STICK, twin))
    keys = [v.key for v in inv.volumes]
    assert len(set(keys)) == 2 and all(k.startswith("u-7fdb-f2ec-") for k in keys)
