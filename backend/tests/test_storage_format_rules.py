"""Assistant de formatage : logique PURE (analyse des disques, identité, cascade de refus, jeton, options). Aucun matériel."""

import json

import pytest

from app.storage.formatting import options as opt
from app.storage.formatting.disks import parse_disks
from app.storage.formatting.model import DiskInfo, PartInfo, fingerprint, inventory_digest
from app.storage.formatting.refusals import REFUSALS, FormatRefusal
from app.storage.formatting.rules import GuardContext, candidates, evaluate, first_refusal
from app.storage.formatting.tokens import PlanTokens

GIB = 1024 ** 3


def part(name="sdb1", fstype="exfat", label="CLUB", uuid="AAAA-0001", size=60 * GIB, mounts=(), partn="1", ro=False, start=2048):
    return PartInfo(name=name, path=f"/dev/{name}", fstype=fstype, label=label, uuid=uuid, size_bytes=size, mountpoints=tuple(mounts),
                    partn=partn, read_only=ro, start_sectors=start)


def disk(name="sdb", parts=None, **kw):
    base = dict(name=name, path=f"/dev/{name}", dev_type="disk", size_bytes=64 * GIB, vendor="SanDisk", model="Ultra", serial="4C530001234567",
                transport="usb", removable=True, hotplug=True, read_only=False, rotational=False, ptable="gpt", sd_card=False, kind="usb",
                partitions=tuple(parts if parts is not None else [part()]))
    base.update(kw)
    return DiskInfo(**base)


def ctx(d, **kw):
    return GuardContext(supported=True, disk=d, protected_paths=["/home/fanta/.local/share/bobine"], **kw)


def refusal_code(c):
    bad = first_refusal(evaluate(c))
    return bad.code if bad else None


# --------------------------------------------------------------------------------------------------- analyse de lsblk
LSBLK = {
    "blockdevices": [
        {"name": "nvme0n1", "path": "/dev/nvme0n1", "type": "disk", "size": 512 * GIB, "rm": False, "hotplug": False, "tran": "nvme", "pttype": "gpt",
         "children": [
             {"name": "nvme0n1p1", "path": "/dev/nvme0n1p1", "type": "part", "fstype": "vfat", "size": GIB, "mountpoints": ["/boot/efi"]},
             {"name": "nvme0n1p2", "path": "/dev/nvme0n1p2", "type": "part", "fstype": "ext4", "size": 400 * GIB, "mountpoints": ["/"]},
         ]},
        {"name": "sdb", "path": "/dev/sdb", "type": "disk", "size": "64000000000", "rm": "1", "hotplug": "1", "tran": "usb", "model": "Ultra", "serial": "4C53",
         "vendor": "SanDisk ", "pttype": "gpt", "ro": "0", "rota": "0",
         "children": [
             {"name": "sdb1", "path": "/dev/sdb1", "type": "part", "fstype": "exfat", "label": "CLUB", "uuid": "AAAA-0001", "size": "31000000000",
              "partn": "1", "start": "2048", "mountpoints": ["/run/media/u/CLUB"]},
             {"name": "sdb2", "path": "/dev/sdb2", "type": "part", "fstype": "crypto_LUKS", "size": "30000000000", "partn": "2", "start": "60546875",
              "mountpoints": [None]},
         ]},
        {"name": "sr0", "path": "/dev/sr0", "type": "rom", "size": 0},
        {"name": "loop4", "path": "/dev/loop4", "type": "loop", "size": 100 * 1024 * 1024, "fstype": "squashfs", "mountpoints": ["/snap/core/1"]},
        {"name": "mmcblk0", "path": "/dev/mmcblk0", "type": "disk", "size": 32 * GIB, "rm": False, "hotplug": False, "pttype": "dos",
         "children": [{"name": "mmcblk0p1", "path": "/dev/mmcblk0p1", "type": "part", "fstype": "vfat", "uuid": "1234-ABCD", "size": 32 * GIB, "partn": "1"}]},
    ]
}


def test_lsblk_becomes_whole_disks_with_every_partition():
    disks = {d.name: d for d in parse_disks(json.dumps(LSBLK), is_sd_card=lambda n: n == "mmcblk0")}
    assert set(disks) == {"nvme0n1", "sdb", "loop4", "mmcblk0"}            # lecteur optique ignoré
    sdb = disks["sdb"]
    assert [p.fstype for p in sdb.partitions] == ["exfat", "crypto_LUKS"]  # y compris la partition que Bobine ne propose jamais
    assert sdb.removable and sdb.hotplug and sdb.transport == "usb" and sdb.ptable == "gpt" and sdb.size_bytes == 64_000_000_000
    assert sdb.partitions[0].start_sectors == 2048 and sdb.partitions[0].mountpoints == ("/run/media/u/CLUB",) and sdb.partitions[1].mountpoints == ()
    assert disks["mmcblk0"].sd_card and disks["loop4"].dev_type == "loop"
    assert disks["nvme0n1"].partitions[1].mountpoints == ("/",)


def test_filesystem_directly_on_the_disk_is_a_whole_disk_entry():
    data = {"blockdevices": [{"name": "sdc", "path": "/dev/sdc", "type": "disk", "size": GIB, "rm": True, "tran": "usb", "fstype": "vfat", "uuid": "1111-2222"}]}
    (d,) = parse_disks(data)
    assert len(d.partitions) == 1 and d.partitions[0].whole_disk and d.ptable is None


# --------------------------------------------------------------------------------------------------- identité
def test_fingerprint_ignores_mounts_but_catches_any_other_change():
    base = disk()
    mounted = disk(parts=[part(mounts=["/run/media/u/CLUB"])])
    assert fingerprint(base) == fingerprint(mounted)
    assert fingerprint(base) != fingerprint(disk(serial="OTHER"))
    assert fingerprint(base) != fingerprint(disk(path="/dev/sdc"))
    assert fingerprint(base) != fingerprint(disk(size_bytes=32 * GIB))
    assert fingerprint(base) != fingerprint(disk(ptable="dos"))
    assert fingerprint(base) != fingerprint(disk(parts=[part(uuid="BBBB-0002")]))
    assert fingerprint(base) != fingerprint(disk(parts=[part(label="AUTRE")]))
    assert fingerprint(base) != fingerprint(disk(parts=[part(), part("sdb2", "ext4", "X", "u2", partn="2")]))


def test_inventory_digest_changes_when_another_support_appears():
    a, b = disk(), disk("sdc", path="/dev/sdc", serial="ZZ")
    assert inventory_digest([a]) == inventory_digest([a])
    assert inventory_digest([a]) != inventory_digest([a, b])
    assert inventory_digest([a, b]) == inventory_digest([b, a])


def test_candidates_are_strictly_removable_and_images_only_when_allowed():
    usb, sd = disk(), disk("mmcblk0", transport=None, removable=False, hotplug=False, sd_card=True)
    internal = disk("nvme0n1", transport="nvme", removable=False, hotplug=False)
    hotplug_only = disk("sdz", transport="sata", removable=False, hotplug=True)
    loop = disk("loop9", dev_type="loop", removable=False, hotplug=False, transport=None)
    assert [d.name for d in candidates([usb, sd, internal, hotplug_only, loop])] == ["sdb", "mmcblk0"]
    assert [d.name for d in candidates([usb, loop], allow_images=True)] == ["sdb", "loop9"]


# --------------------------------------------------------------------------------------------------- cascade de refus
def test_clean_removable_stick_passes_every_check():
    checks = evaluate(ctx(disk()))
    assert all(c.ok for c in checks) and first_refusal(checks) is None
    assert [c.id for c in checks] == ["platform", "present", "allowed", "not_system", "removable", "not_bobine_data", "not_registered",
                                      "not_in_use", "single_operation", "writable", "not_stacked", "size"]


def test_every_refusal_has_its_clear_code():
    assert refusal_code(GuardContext(supported=False, disk=disk())) == "format_unsupported_platform"
    assert refusal_code(GuardContext(supported=True, disk=None)) == "format_not_found"
    # disque système : un montage système ou un swap, même sur un disque USB
    assert refusal_code(ctx(disk(parts=[part(fstype="ext4", mounts=["/"])]))) == "format_system_disk"
    assert refusal_code(ctx(disk(parts=[part(mounts=["/boot/efi"])]))) == "format_system_disk"
    assert refusal_code(ctx(disk(parts=[part(mounts=["/home"])]))) == "format_system_disk"
    assert refusal_code(ctx(disk(parts=[part(fstype="swap")]))) == "format_system_disk"
    assert refusal_code(ctx(disk(parts=[part(mounts=["/snap/core/1"])]))) == "format_system_disk"
    # disque interne fixe
    internal = disk("nvme0n1", transport="nvme", removable=False, hotplug=False, parts=[part("nvme0n1p1", mounts=[])])
    assert refusal_code(ctx(internal)) == "format_internal_disk"
    assert refusal_code(ctx(disk("sdz", transport="sata", removable=False, hotplug=True))) == "format_internal_disk"   # HOTPLUG seul ne suffit pas
    assert refusal_code(ctx(disk("sdy", transport=None, removable=False, hotplug=False))) == "format_not_removable"
    # dossiers de données de Bobine : même chemin, chemin contenu, chemin contenant, même périphérique
    for mount in ("/home/fanta/.local/share/bobine", "/home/fanta/.local/share/bobine/media", "/home/fanta"):
        assert refusal_code(ctx(disk(parts=[part(mounts=[mount])]))) == "format_bobine_data", mount
    same_device = GuardContext(disk=disk(parts=[part(mounts=["/mnt/x"])]), protected_paths=["/srv/elsewhere"], protected_devs=frozenset({77}), mount_devs={"/mnt/x": 77})
    assert refusal_code(same_device) == "format_bobine_data"
    # bibliothèque externe enregistrée : action proposée
    registered = evaluate(ctx(disk(), registered_uuids=frozenset({"aaaa-0001"})))
    bad = first_refusal(registered)
    assert bad.code == "format_library_registered" and bad.actions and bad.actions[0]["id"] == "unregister"
    # opérations en cours
    assert refusal_code(ctx(disk(), in_use=True)) == "format_in_use"
    assert refusal_code(ctx(disk(), other_format_active=True)) == "format_busy_operation"
    # protégé en écriture
    assert refusal_code(ctx(disk(read_only=True))) == "format_read_only"
    assert refusal_code(ctx(disk(parts=[part(ro=True)]))) == "format_read_only"
    # chiffré, RAID, LVM
    for fs in ("crypto_LUKS", "linux_raid_member", "LVM2_member", "zfs_member"):
        assert refusal_code(ctx(disk(parts=[part(fstype=fs)]))) == "format_encrypted_stack", fs
    # images disque : refusées par défaut
    assert refusal_code(ctx(disk("loop3", dev_type="loop", removable=False, transport=None, hotplug=False))) == "format_image_not_allowed"
    assert refusal_code(ctx(disk("loop3", dev_type="loop", removable=False, transport=None, hotplug=False), allow_images=True)) is None
    # trop petit
    assert refusal_code(ctx(disk(size_bytes=10 * 1024 * 1024))) == "format_too_small"
    # liste blanche d'essai : un autre périphérique est refusé même s'il est parfaitement amovible
    assert refusal_code(ctx(disk(), allowlist=frozenset({"/dev/loop29"}))) == "format_not_allowed"
    assert refusal_code(ctx(disk("loop29", path="/dev/loop29", dev_type="loop", removable=False, transport=None, hotplug=False), allow_images=True, allowlist=frozenset({"/dev/loop29"}))) is None


def test_cascade_order_system_before_removable_and_first_failure_wins():
    # un disque interne portant « / » doit être dit « système » (la raison la plus grave), pas seulement « interne »
    system = disk("nvme0n1", transport="nvme", removable=False, hotplug=False, parts=[part("nvme0n1p2", "ext4", mounts=["/"])])
    assert refusal_code(ctx(system)) == "format_system_disk"
    # plusieurs refus : le premier de la cascade est opposé
    many = disk(read_only=True, parts=[part(fstype="LVM2_member", mounts=["/home/fanta/.local/share/bobine/x"])])
    assert refusal_code(ctx(many, in_use=True)) == "format_bobine_data"


def test_every_code_used_by_the_rules_is_documented_with_a_message():
    for code, (status, message) in REFUSALS.items():
        assert code.startswith("format_") and 400 <= status < 600 and message and "/dev/" not in message


def test_simulated_etoile_identity_is_refused_when_registered_or_in_use_or_off_allowlist():
    """Identité du vrai disque « Étoile » (exFAT, 238 Go, USB) SIMULÉE : aucun accès au vrai périphérique."""
    etoile = disk("sdq", size_bytes=255_800_000_000, vendor="Generic", model="USB Flash", serial="ETOILE0000",
                  parts=[part("sdq1", "exfat", "Étoile", "E7E7-0238", 255_700_000_000)])
    assert refusal_code(ctx(etoile)) is None                                                    # une clé quelconque serait formatable...
    assert refusal_code(ctx(etoile, registered_uuids=frozenset({"e7e7-0238"}))) == "format_library_registered"   # ...pas une bibliothèque enregistrée
    assert refusal_code(ctx(etoile, in_use=True)) == "format_in_use"
    assert refusal_code(ctx(etoile, allowlist=frozenset({"/dev/loop29"}))) == "format_not_allowed"                 # ni hors de la liste blanche d'essai


# --------------------------------------------------------------------------------------------------- jeton
class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make_tokens(clock):
    return PlanTokens(clock=clock, ttl=120.0, min_age=4.0)


def code_of(fn, *a, **kw):
    with pytest.raises(FormatRefusal) as info:
        fn(*a, **kw)
    return info.value.code


def test_token_is_single_use_and_short_lived():
    clock = Clock()
    tokens = make_tokens(clock)
    token = tokens.issue(key="u-x", identity="id", inventory="inv", owner="10.0.0.1")
    assert code_of(tokens.check_age, token) == "format_too_early"          # délai de réflexion imposé côté serveur
    clock.now += 5
    tokens.check_age(token)
    record = tokens.consume(token, owner="10.0.0.1")
    assert (record.key, record.identity, record.inventory) == ("u-x", "id", "inv")
    assert code_of(tokens.consume, token, owner="10.0.0.1") == "format_token_used"     # usage unique


def test_token_expires_after_two_minutes_and_is_bound_to_its_requester():
    clock = Clock()
    tokens = make_tokens(clock)
    token = tokens.issue(key="u-x", identity="id", inventory="inv", owner="10.0.0.1")
    clock.now += 10
    assert code_of(tokens.consume, token, owner="10.0.0.2") == "format_token_owner"
    still = tokens.issue(key="u-x", identity="id", inventory="inv", owner="10.0.0.1")
    clock.now += 121
    assert code_of(tokens.consume, still, owner="10.0.0.1") == "format_token_expired"
    assert code_of(tokens.consume, "inventé", owner="10.0.0.1") == "format_token_unknown"
    assert code_of(tokens.consume, None, owner="10.0.0.1") == "format_token_missing"
    assert code_of(tokens.consume, "", owner="10.0.0.1") == "format_token_missing"


def test_token_is_random_and_never_stored_in_clear():
    tokens = make_tokens(Clock())
    a = tokens.issue(key="k", identity="i", inventory="v", owner="o")
    b = tokens.issue(key="k", identity="i", inventory="v", owner="o")
    assert a != b and len(a) >= 30
    assert a not in tokens._live and all(len(h) == 64 for h in tokens._live)


# --------------------------------------------------------------------------------------------------- options
def test_labels_are_validated_per_filesystem():
    assert opt.normalize_label("exfat", "  Salle 1 ") == "Salle 1"
    assert opt.normalize_label("vfat", "cours_a") == "COURS_A"                       # FAT32 : majuscules
    assert opt.normalize_label("ext4", "é" * 8) == "é" * 8                            # 16 octets
    for fs, bad, code in (("exfat", "", "label_empty"), ("exfat", "x" * 12, "label_too_long"), ("vfat", "x" * 12, "label_too_long"),
                          ("ext4", "é" * 9, "label_too_long"), ("exfat", "a/b", "label_chars"), ("exfat", 'a"b', "label_chars"),
                          ("vfat", "a.b", "label_chars"), ("vfat", "é", "label_chars"), ("exfat", "a\nb", "label_chars"), ("nope", "x", "fs_unknown")):
        with pytest.raises(opt.LabelError) as info:
            opt.normalize_label(fs, bad)
        assert info.value.code == code, (fs, bad)


def test_mkfs_parameters_follow_the_capacity_and_use():
    assert opt.exfat_cluster_bytes(100 * 1024 ** 2) == 4096
    assert opt.exfat_cluster_bytes(16 * GIB) == 32768
    assert opt.exfat_cluster_bytes(238 * GIB) == 131072
    assert opt.mkfs_args("exfat", 238 * GIB) == ["-c", "131072"]
    assert opt.mkfs_args("ext4", 4 * GIB) == ["-m", "0"]                              # aucun bloc réservé
    assert opt.mkfs_args("ext4", 238 * GIB) == ["-m", "0", "-T", "largefile"]
    assert opt.mkfs_args("vfat", GIB) == ["-F", "32"]
    assert "-f" not in opt.mkfs_args("ntfs", GIB) and "--full-format" not in opt.mkfs_args("exfat", GIB)   # jamais d'écrasement complet
    assert opt.partition_bytes_for(64 * GIB) == 64 * GIB - 2 * 1024 * 1024
    assert opt.capacity_limit("vfat", 3 * 1024 ** 4) == "fat32_over_2tib" and opt.capacity_limit("exfat", 3 * 1024 ** 4) is None


def test_confirmation_text_is_the_name_then_the_serial_tail():
    named = disk()
    assert opt.confirm_expected(named) == {"mode": "name", "expected": "CLUB"}
    assert opt.confirm_matches(named, "  club ") and not opt.confirm_matches(named, "cl") and not opt.confirm_matches(named, "")
    anonymous = disk(parts=[part(label=None)])
    assert opt.confirm_expected(anonymous) == {"mode": "serial_tail", "expected": "4567"}
    assert opt.confirm_matches(anonymous, "4567") and not opt.confirm_matches(anonymous, "club")
    bare = disk(parts=[part(label=None)], serial=None)
    assert opt.confirm_expected(bare)["mode"] == "model"
    assert opt.confirm_expected(disk(parts=[part(label=None)], serial=None, vendor=None, model=None)) == {"mode": "word", "expected": "ERASE"}


def test_option_rows_carry_verdict_availability_and_longevity_notes():
    d = disk()
    exfat = opt.option_for("exfat", d, tool_present=True, others=("windows",), media="flash")
    assert exfat["available"] and exfat["verdict"] == "recommended" and "no_journal_unplug_risk" in exfat["notes"] and "quick_format_only" in exfat["notes"]
    assert exfat["label_max"] == 11 and exfat["cluster_bytes"] == 131072 and exfat["label"] == "CLUB"
    ext4 = opt.option_for("ext4", d, tool_present=True, others=(), media="flash")
    assert ext4["verdict"] == "recommended" and "journal_unplug_ok" in ext4["notes"]
    missing = opt.option_for("ntfs", d, tool_present=False, others=(), media="flash")
    assert not missing["available"] and missing["unavailable"] == "tool_missing" and missing["install_package"] == "ntfs-3g"
    big = opt.option_for("vfat", disk(size_bytes=3 * 1024 ** 4), tool_present=True, others=(), media="flash")
    assert not big["available"] and big["unavailable"] == "fat32_over_2tib"
