"""Santé d'un support : analyse de `smartctl -j -a` (logique PURE) et avertissements."""

from __future__ import annotations

import json
from typing import Any

_ATA_WEAR_IDS = {177: "Wear_Leveling_Count", 231: "SSD_Life_Left", 233: "Media_Wearout_Indicator", 202: "Percent_Lifetime_Remain"}

TEMP_WARN_C = 55
TEMP_CRIT_C = 65
WEAR_WARN_PERCENT = 80
WEAR_CRIT_PERCENT = 95
REALLOCATED_CRIT = 100


def unavailable(reason: str, message: str | None = None) -> dict[str, Any]:
    return {"available": False, "reason": reason, "message": message, "status": "unknown", "warnings": []}


def _messages(report: dict[str, Any]) -> list[str]:
    return [str(m.get("string", "")) for m in (report.get("smartctl", {}).get("messages") or []) if isinstance(m, dict)]


def _raw(table: list[dict[str, Any]], attr_id: int) -> int | None:
    for row in table:
        if row.get("id") == attr_id:
            value = (row.get("raw") or {}).get("value")
            return int(value) if isinstance(value, (int, float)) else None
    return None


class _Findings:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.critical = False

    def add(self, code: str, critical: bool = False) -> None:
        self.warnings.append(code)
        self.critical = self.critical or critical

    def level(self, value, code: str, warn_at: float, crit_at: float) -> None:
        if isinstance(value, (int, float)) and value >= crit_at:
            self.add(f"{code}_critical", True)
        elif isinstance(value, (int, float)) and value >= warn_at:
            self.add(f"{code}_high")


def _number(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _refusal(report: dict) -> dict[str, Any] | None:
    messages = " ".join(_messages(report)).lower()
    exit_status = int(report.get("smartctl", {}).get("exit_status") or 0)
    if "permission denied" in messages or "operation not permitted" in messages or (exit_status & 0b10 and not report.get("device")):
        return unavailable("permission", "Droits insuffisants pour lire SMART (smartctl exige l'administrateur).")
    if "no such device" in messages or "no such file" in messages:
        return unavailable("device_removed")
    has_data = any(k in report for k in ("ata_smart_attributes", "nvme_smart_health_information_log", "smart_status"))
    if not has_data or (report.get("smart_support") or {}).get("available") is False:
        return unavailable("no_smart", "Ce support ne fournit pas de données SMART (fréquent pour une clé USB ou une carte SD).")
    return None


def _nvme_health(nvme: dict, found: _Findings) -> dict[str, Any]:
    spare = _number(nvme.get("available_spare"))
    units = nvme.get("data_units_written")
    media_errors = nvme.get("media_errors") if isinstance(nvme.get("media_errors"), int) else None
    if nvme.get("critical_warning"):
        found.add("nvme_critical_warning", True)
    threshold = nvme.get("available_spare_threshold")
    if spare is not None and isinstance(threshold, (int, float)) and spare < threshold:
        found.add("spare_below_threshold", True)
    elif spare is not None and spare <= 20:
        found.add("spare_low")
    if media_errors:
        found.add("media_errors")
    return {
        "wear_percent_used": _number(nvme.get("percentage_used")),
        "spare_percent": spare,
        "media_errors": media_errors,
        "bytes_written_device": int(units) * 512_000 if isinstance(units, (int, float)) else None,
    }


def _ata_wear(table: list[dict]) -> float | None:
    for attr_id in _ATA_WEAR_IDS:
        row = next((r for r in table if r.get("id") == attr_id and isinstance(r.get("value"), (int, float))), None)
        if row is not None:
            return max(0.0, 100.0 - float(row["value"]))
    return None


def parse_smartctl(output: str | dict[str, Any]) -> dict[str, Any]:
    """Résume la sortie JSON de smartctl en rapport de santé (voir `unavailable` pour les échecs)."""
    try:
        report = json.loads(output) if isinstance(output, str) else output
    except ValueError:
        return unavailable("no_smart", "Sortie smartctl illisible.")
    if not isinstance(report, dict):
        return unavailable("no_smart")
    refusal = _refusal(report)
    if refusal:
        return refusal
    found = _Findings()
    passed = (report.get("smart_status") or {}).get("passed")
    if passed is False:
        found.add("smart_failed", True)
    nvme = report.get("nvme_smart_health_information_log") or {}
    temperature = (report.get("temperature") or {}).get("current")
    if temperature is None:
        temperature = nvme.get("temperature")
    hours = (report.get("power_on_time") or {}).get("hours")
    table = (report.get("ata_smart_attributes") or {}).get("table") or []
    reallocated, pending, uncorrectable = _raw(table, 5), _raw(table, 197), _raw(table, 198)
    wear = _nvme_health(nvme, found) if nvme else {
        "wear_percent_used": _ata_wear(table), "spare_percent": None, "media_errors": None, "bytes_written_device": None,
    }
    if reallocated:
        found.add("reallocated_sectors", reallocated >= REALLOCATED_CRIT)
    if pending:
        found.add("pending_sectors")
    if uncorrectable:
        found.add("uncorrectable_sectors", True)
    found.level(wear["wear_percent_used"], "wear", WEAR_WARN_PERCENT, WEAR_CRIT_PERCENT)
    found.level(temperature, "temperature", TEMP_WARN_C, TEMP_CRIT_C)
    return {
        "available": True,
        "reason": None,
        "message": None,
        "status": "critical" if found.critical else ("warning" if found.warnings else "ok"),
        "passed": passed,
        "temperature_c": temperature if isinstance(temperature, (int, float)) else None,
        "power_on_hours": hours if isinstance(hours, (int, float)) else None,
        "reallocated_sectors": reallocated,
        "pending_sectors": pending,
        "uncorrectable_sectors": uncorrectable,
        **wear,
        "model": report.get("model_name"),
        "protocol": (report.get("device") or {}).get("protocol"),
        "warnings": found.warnings,
    }


GIB = 1024**3
WRITE_WARN_BYTES = {"sd": 50 * GIB, "usb": 100 * GIB, "ssd": 1024 * GIB, "hdd": None, "image": None, "other": 100 * GIB}


def write_wear_level(kind: str, bytes_written: int) -> str:
    """`ok`, `warning` (seuil atteint) ou `critical` (trois fois le seuil) pour le compteur d'écritures de Bobine."""
    limit = WRITE_WARN_BYTES.get(kind, WRITE_WARN_BYTES["other"])
    if not limit or bytes_written < limit:
        return "ok"
    return "critical" if bytes_written >= 3 * limit else "warning"


def combine_status(*statuses: str) -> str:
    """Pire état parmi `ok`, `warning`, `critical` ; `unknown` ne masque rien."""
    order = {"ok": 0, "unknown": 0, "warning": 1, "critical": 2}
    worst = max((order.get(s, 0) for s in statuses), default=0)
    return {0: "ok", 1: "warning", 2: "critical"}[worst]
