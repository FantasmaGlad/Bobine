"""Santé d'un support : analyse de `smartctl -j -a` (logique PURE) et avertissements.

`smartctl` exige en général des droits d'administrateur ; sans eux, ou pour une clé USB / une carte SD
(pas de SMART), le résultat est honnête : `available: false` avec une raison (`permission`, `no_smart`,
`tool_missing`, `device_removed`), jamais une valeur inventée."""

from __future__ import annotations

import json
from typing import Any

# Attributs ATA d'usure SSD : la valeur normalisée vaut 100 neuf et descend vers 0 (restant, pas usé).
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


def parse_smartctl(output: str | dict[str, Any]) -> dict[str, Any]:
    """Résume la sortie JSON de smartctl en rapport de santé (voir `unavailable` pour les échecs)."""
    try:
        report = json.loads(output) if isinstance(output, str) else output
    except ValueError:
        return unavailable("no_smart", "Sortie smartctl illisible.")
    if not isinstance(report, dict):
        return unavailable("no_smart")

    messages = " ".join(_messages(report)).lower()
    exit_status = int(report.get("smartctl", {}).get("exit_status") or 0)
    if "permission denied" in messages or "operation not permitted" in messages or (exit_status & 0b10 and not report.get("device")):
        return unavailable("permission", "Droits insuffisants pour lire SMART (smartctl exige l'administrateur).")
    if "no such device" in messages or "no such file" in messages:
        return unavailable("device_removed")
    smart_supported = (report.get("smart_support") or {}).get("available")
    has_data = any(k in report for k in ("ata_smart_attributes", "nvme_smart_health_information_log", "smart_status"))
    if not has_data or smart_supported is False:
        return unavailable("no_smart", "Ce support ne fournit pas de données SMART (fréquent pour une clé USB ou une carte SD).")

    warnings: list[str] = []
    critical = False
    passed = (report.get("smart_status") or {}).get("passed")
    if passed is False:
        warnings.append("smart_failed")
        critical = True

    temperature = (report.get("temperature") or {}).get("current")
    nvme = report.get("nvme_smart_health_information_log") or {}
    if temperature is None:
        temperature = nvme.get("temperature")
    hours = (report.get("power_on_time") or {}).get("hours")
    table = (report.get("ata_smart_attributes") or {}).get("table") or []

    reallocated = _raw(table, 5)
    pending = _raw(table, 197)
    uncorrectable = _raw(table, 198)
    wear_used: float | None = None
    spare: float | None = None
    media_errors: int | None = None
    written: int | None = None

    if nvme:
        used = nvme.get("percentage_used")
        wear_used = float(used) if isinstance(used, (int, float)) else None
        spare_value = nvme.get("available_spare")
        spare = float(spare_value) if isinstance(spare_value, (int, float)) else None
        media_errors = nvme.get("media_errors") if isinstance(nvme.get("media_errors"), int) else None
        units = nvme.get("data_units_written")
        written = int(units) * 512_000 if isinstance(units, (int, float)) else None  # unité NVMe : 1000 secteurs de 512 octets
        if nvme.get("critical_warning"):
            warnings.append("nvme_critical_warning")
            critical = True
        threshold = nvme.get("available_spare_threshold")
        if spare is not None and isinstance(threshold, (int, float)) and spare < threshold:
            warnings.append("spare_below_threshold")
            critical = True
        elif spare is not None and spare <= 20:
            warnings.append("spare_low")
        if media_errors:
            warnings.append("media_errors")
    else:
        for attr_id in _ATA_WEAR_IDS:
            for row in table:
                if row.get("id") == attr_id and isinstance(row.get("value"), (int, float)):
                    wear_used = max(0.0, 100.0 - float(row["value"]))
                    break
            if wear_used is not None:
                break

    if reallocated:
        warnings.append("reallocated_sectors")
        if reallocated >= REALLOCATED_CRIT:
            critical = True
    if pending:
        warnings.append("pending_sectors")
    if uncorrectable:
        warnings.append("uncorrectable_sectors")
        critical = True
    if wear_used is not None:
        if wear_used >= WEAR_CRIT_PERCENT:
            warnings.append("wear_critical")
            critical = True
        elif wear_used >= WEAR_WARN_PERCENT:
            warnings.append("wear_high")
    if isinstance(temperature, (int, float)):
        if temperature >= TEMP_CRIT_C:
            warnings.append("temperature_critical")
            critical = True
        elif temperature >= TEMP_WARN_C:
            warnings.append("temperature_high")

    status = "critical" if critical else ("warning" if warnings else "ok")
    return {
        "available": True,
        "reason": None,
        "message": None,
        "status": status,
        "passed": passed,
        "temperature_c": temperature if isinstance(temperature, (int, float)) else None,
        "power_on_hours": hours if isinstance(hours, (int, float)) else None,
        "reallocated_sectors": reallocated,
        "pending_sectors": pending,
        "uncorrectable_sectors": uncorrectable,
        "wear_percent_used": wear_used,
        "spare_percent": spare,
        "media_errors": media_errors,
        "bytes_written_device": written,
        "model": report.get("model_name"),
        "protocol": (report.get("device") or {}).get("protocol"),
        "warnings": warnings,
    }


# --- avertissements d'usure fondés sur les écritures de Bobine ------------------------------------------------

GIB = 1024**3
# Seuils indicatifs d'octets écrits PAR BOBINE (export vers le support) avant d'avertir, par nature de support.
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
