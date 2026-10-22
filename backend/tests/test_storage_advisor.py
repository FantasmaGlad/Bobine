"""Stockage externe : conseiller de système de fichiers, santé SMART, longévité (logique pure)."""

import pytest

from app.storage import fsadvisor, health, longevity


def codes(a):
    return set(a.notes)


def test_recommendation_by_host_and_other_oses():
    assert fsadvisor.recommend_format("linux")["fstype"] == "ext4"
    assert fsadvisor.recommend_format("windows")["fstype"] == "ntfs"
    assert fsadvisor.recommend_format("macos", media="ssd")["fstype"] == "apfs"
    assert fsadvisor.recommend_format("macos", media="hdd")["fstype"] == "hfsplus"
    travel = fsadvisor.recommend_format("linux", ("windows", "macos"))
    assert travel["fstype"] == "exfat" and "no_journal_unplug_risk" in travel["notes"] and "prefer_read_only" in travel["notes"]
    assert fsadvisor.recommend_format("android")["fstype"] == "exfat"
    assert "android_ext4_unmounted" in fsadvisor.recommend_format("android")["notes"]
    legacy = fsadvisor.recommend_format("linux", legacy_readers=True)
    assert legacy["fstype"] == "vfat" and "file_limit_4gib" in legacy["notes"]


def test_recommendation_never_formats_and_shows_procedures():
    rec = fsadvisor.recommend_format("linux", ("windows",))
    assert rec["destructive"] is True
    assert any("mkfs.exfat" in step for step in rec["procedures"]["linux"])
    assert "windows" in rec["procedures"] and "macos" in rec["procedures"]
    assert not hasattr(fsadvisor, "format_volume")  # aucune fonction d'exécution


def test_unknown_inputs_fall_back_safely():
    rec = fsadvisor.recommend_format("plan9", ("linux", "bogus"), "tape")
    assert rec["host_os"] == "linux" and rec["media"] == "flash" and rec["other_oses"] == []


def test_assessment_per_filesystem():
    ext4 = fsadvisor.assess_filesystem("ext4")
    assert ext4.verdict == fsadvisor.RECOMMENDED and ext4.journal is True and ext4.permissions is True and "no_file_limit" in codes(ext4)
    exfat_solo = fsadvisor.assess_filesystem("exfat")
    assert exfat_solo.verdict == fsadvisor.ACCEPTABLE and "no_journal_unplug_risk" in codes(exfat_solo) and "prefer_read_only" in codes(exfat_solo)
    exfat_travel = fsadvisor.assess_filesystem("exfat", other_oses=("windows", "macos"))
    assert exfat_travel.verdict == fsadvisor.RECOMMENDED
    fat = fsadvisor.assess_filesystem("vfat", use="library")
    assert fat.verdict == fsadvisor.DISCOURAGED and fat.max_file_gib == 4 and "file_limit_4gib" in codes(fat)
    assert fsadvisor.assess_filesystem("fat32").fstype == "vfat"
    ntfs = fsadvisor.assess_filesystem("ntfs", host_os="linux")
    assert ntfs.verdict == fsadvisor.ACCEPTABLE and "ntfs_unclean_risk" in codes(ntfs)
    assert fsadvisor.assess_filesystem("ntfs", host_os="windows").verdict == fsadvisor.RECOMMENDED
    assert fsadvisor.assess_filesystem("apfs", host_os="linux").verdict == fsadvisor.DISCOURAGED
    assert fsadvisor.assess_filesystem("apfs", host_os="linux").write_allowed is False
    unknown = fsadvisor.assess_filesystem("zfs_member")
    assert unknown.verdict == "unknown" and unknown.write_allowed is False


def test_dirty_volume_is_never_writable():
    dirty = fsadvisor.assess_filesystem("ntfs", dirty=True)
    assert dirty.verdict == fsadvisor.DISCOURAGED and dirty.reason == "dirty" and dirty.write_allowed is False
    assert "dirty_repair_first" in codes(dirty)


def test_flash_media_notes_wear():
    assert "flash_write_wear" in codes(fsadvisor.assess_filesystem("ext4", media="flash"))
    assert "flash_write_wear" not in codes(fsadvisor.assess_filesystem("ext4", media="hdd"))


# ---------------------------------------------------------------------------------------------------------
# SMART
# ---------------------------------------------------------------------------------------------------------

def ata(attrs, passed=True, temp=34, hours=1200):
    return {
        "smartctl": {"exit_status": 0}, "device": {"protocol": "ATA"}, "model_name": "SSD", "smart_support": {"available": True},
        "smart_status": {"passed": passed}, "temperature": {"current": temp}, "power_on_time": {"hours": hours},
        "ata_smart_attributes": {"table": [{"id": i, "name": n, "value": v, "raw": {"value": raw}} for i, n, v, raw in attrs]},
    }


def test_smart_healthy_ssd():
    report = health.parse_smartctl(ata([(5, "Reallocated", 100, 0), (177, "Wear_Leveling_Count", 97, 30), (197, "Pending", 100, 0)]))
    assert report["available"] and report["status"] == "ok" and report["wear_percent_used"] == 3.0 and report["warnings"] == []
    assert report["temperature_c"] == 34 and report["power_on_hours"] == 1200


def test_smart_failures_and_warnings():
    failing = health.parse_smartctl(ata([(5, "R", 100, 0)], passed=False))
    assert failing["status"] == "critical" and "smart_failed" in failing["warnings"]
    realloc = health.parse_smartctl(ata([(5, "R", 100, 8)]))
    assert realloc["status"] == "warning" and "reallocated_sectors" in realloc["warnings"]
    assert health.parse_smartctl(ata([(5, "R", 100, 150)]))["status"] == "critical"
    assert "uncorrectable_sectors" in health.parse_smartctl(ata([(198, "U", 100, 2)]))["warnings"]
    worn = health.parse_smartctl(ata([(231, "SSD_Life_Left", 12, 0)]))
    assert worn["wear_percent_used"] == 88.0 and "wear_high" in worn["warnings"] and worn["status"] == "warning"
    assert health.parse_smartctl(ata([(231, "SSD_Life_Left", 3, 0)]))["status"] == "critical"
    assert "temperature_high" in health.parse_smartctl(ata([], temp=58))["warnings"]
    assert health.parse_smartctl(ata([], temp=70))["status"] == "critical"


def test_smart_nvme():
    nvme = {"smartctl": {"exit_status": 0}, "device": {"protocol": "NVMe"}, "smart_support": {"available": True}, "smart_status": {"passed": True},
            "nvme_smart_health_information_log": {"percentage_used": 82, "available_spare": 15, "available_spare_threshold": 10,
                                                  "media_errors": 0, "temperature": 41, "data_units_written": 2_000_000, "critical_warning": 0}}
    report = health.parse_smartctl(nvme)
    assert report["wear_percent_used"] == 82 and "wear_high" in report["warnings"] and "spare_low" in report["warnings"]
    assert report["bytes_written_device"] == 2_000_000 * 512_000
    nvme["nvme_smart_health_information_log"]["available_spare"] = 5
    assert health.parse_smartctl(nvme)["status"] == "critical"


def test_smart_unavailable_is_honest():
    perm = health.parse_smartctl({"smartctl": {"exit_status": 2, "messages": [{"string": "Smartctl open device: /dev/sda failed: Permission denied"}]}})
    assert perm == {**perm, "available": False, "reason": "permission", "status": "unknown"}
    nosmart = health.parse_smartctl({"smartctl": {"exit_status": 4, "messages": [{"string": "Unknown USB bridge [0x1234:0x5678 (0x100)]"}]}})
    assert nosmart["available"] is False and nosmart["reason"] == "no_smart"
    assert health.parse_smartctl("pas du json")["reason"] == "no_smart"
    assert health.parse_smartctl({"smartctl": {"messages": [{"string": "No such device"}]}})["reason"] == "device_removed"


def test_write_wear_levels_and_combined_status():
    gib = 1024**3
    assert health.write_wear_level("sd", 10 * gib) == "ok"
    assert health.write_wear_level("sd", 50 * gib) == "warning"
    assert health.write_wear_level("sd", 160 * gib) == "critical"
    assert health.write_wear_level("hdd", 10**15) == "ok"
    assert health.combine_status("ok", "warning") == "warning" and health.combine_status("unknown", "ok") == "ok"
    assert health.combine_status("warning", "critical") == "critical"


# ---------------------------------------------------------------------------------------------------------
# Longévité
# ---------------------------------------------------------------------------------------------------------

def test_defaults_are_read_only_noatime_noexec():
    assert longevity.mount_options(longevity.DEFAULTS, writable=False) == ["ro", "noatime", "nodiratime", "noexec"]
    assert longevity.mount_options(longevity.DEFAULTS, writable=True)[0] == "rw"
    off = longevity.normalize_settings({"noatime": False, "noexec": False})
    assert longevity.mount_options(off, writable=False) == ["ro"]


def test_forbidden_options_are_never_produced():
    for settings in (longevity.DEFAULTS, longevity.normalize_settings({"noatime": False})):
        for writable in (True, False):
            assert not set(longevity.mount_options(settings, writable=writable)) & longevity.FORBIDDEN_OPTIONS


def test_normalize_settings_is_strict():
    s = longevity.normalize_settings({"read_only": "oui", "standby_minutes": 9999, "inconnu": 1, "smart_monitor": False})
    assert s["read_only"] is True and s["standby_minutes"] == 240 and s["smart_monitor"] is False and "inconnu" not in s
    assert longevity.normalize_settings({"standby_minutes": True})["standby_minutes"] == longevity.DEFAULTS["standby_minutes"]
    assert longevity.normalize_settings({"standby_minutes": -5})["standby_minutes"] == 0


def facts(**kw):
    base = dict(mounted=True, mounted_read_only=True, mount_options=("ro", "noatime", "noexec"), rotational=False, discard_supported=True,
                is_root=False, fstrim_timer_enabled=True, standby_supported=True, smart_available=False, smart_reason="permission")
    base.update(kw)
    return longevity.Facts(**base)


def by_id(items):
    return {i["id"]: i for i in items}


def test_report_is_honest_about_what_is_applied():
    items = by_id(longevity.report(longevity.DEFAULTS, facts()))
    assert items["read_only"]["status"] == "applied" and items["noatime"]["status"] == "applied" and items["noexec"]["status"] == "applied"
    assert items["safe_eject"]["status"] == "applied"
    assert items["trim"]["status"] == "applied" and items["trim"]["reason"] == "system_timer"
    assert items["standby"]["status"] == "unavailable" and items["standby"]["reason"] == "not_rotational"
    assert items["smart"]["status"] == "unavailable" and items["smart"]["reason"] == "permission"


def test_report_mounted_rw_by_desktop_is_not_claimed_read_only():
    items = by_id(longevity.report(longevity.DEFAULTS, facts(mounted_read_only=False, mount_options=("rw",))))
    assert items["read_only"]["status"] == "inactive" and items["noatime"]["status"] == "inactive"


def test_report_trim_needs_root_without_timer():
    assert by_id(longevity.report(longevity.DEFAULTS, facts(fstrim_timer_enabled=False)))["trim"]["status"] == "unavailable"
    assert by_id(longevity.report(longevity.DEFAULTS, facts(fstrim_timer_enabled=None)))["trim"]["reason"] == "needs_root"
    assert by_id(longevity.report(longevity.DEFAULTS, facts(discard_supported=False)))["trim"]["reason"] == "no_discard_support"
    assert by_id(longevity.report(longevity.DEFAULTS, facts(is_root=True, fstrim_timer_enabled=False)))["trim"]["status"] == "applied"


def test_report_standby_rules_and_disabled_settings():
    hdd = facts(rotational=True)
    assert by_id(longevity.report(longevity.DEFAULTS, hdd))["standby"]["status"] == "applied"
    assert by_id(longevity.report(longevity.DEFAULTS, facts(rotational=True, standby_supported=False)))["standby"]["reason"] == "standby_not_permitted"
    off = longevity.normalize_settings({"standby_minutes": 0, "read_only": False, "smart_monitor": False})
    items = by_id(longevity.report(off, hdd))
    assert items["standby"]["status"] == "disabled" and items["read_only"]["status"] == "disabled" and items["smart"]["status"] == "disabled"
    unmounted = by_id(longevity.report(longevity.DEFAULTS, facts(mounted=False, mounted_read_only=None, mount_options=())))
    assert unmounted["read_only"]["status"] == "inactive" and unmounted["read_only"]["reason"] == "not_mounted"
