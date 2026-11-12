"""Télémétrie assemblée : durée de fonctionnement, instantanés en base, purge."""

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import psutil

from .cpu import get_cpu_model_name, get_cpu_percent, get_cpu_temp
from .disk import get_storage_model, get_storage_usage
from .gpu import get_gpu_info
from .memory import get_ram_info
from .power import (
    get_average_power_watts,
    get_cumulative_energy_wh,
    get_power_watts,
    update_cumulative_energy,
)
from .probe import _SERVICE_START_TIME, is_android_system

logger = logging.getLogger(__name__)


def get_runtime_info() -> dict[str, Any]:
    """Retourne les informations d'uptime du système et de runtime de Bobine."""
    now = time.time()
    service_uptime = int(now - _SERVICE_START_TIME)

    system_uptime = 0
    is_android = is_android_system()

    if is_android:
        try:
            from android.os import SystemClock
            system_uptime = int(SystemClock.elapsedRealtime() / 1000)
        except Exception as exc:
            logger.debug("get_runtime_info : %s", exc)

    if system_uptime <= 0 and os.path.exists("/proc/uptime"):
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as f:
                system_uptime = int(float(f.read().split()[0]))
        except Exception as exc:
            logger.debug("get_runtime_info : %s", exc)

    if system_uptime <= 0:
        try:
            system_uptime = int(now - psutil.boot_time())
        except Exception:
            system_uptime = service_uptime

    avg_w = get_average_power_watts()
    wh = get_cumulative_energy_wh()

    return {
        "service_uptime_seconds": service_uptime,
        "service_uptime_formatted": format_duration_short(service_uptime),
        "app_runtime_formatted": format_duration_short(service_uptime),
        "system_uptime_seconds": system_uptime,
        "system_uptime_formatted": format_duration_short(system_uptime),
        "uptime_formatted": format_duration_short(system_uptime),
        "cumulative_energy_wh": wh if wh > 0 else None,
        "average_power_watts": avg_w,
    }


def format_duration_short(seconds: int) -> str:
    """Formate une durée en 'Xj Yh Zm' ou 'Yh Zm'."""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days > 0:
        return f"{days}j {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def get_system_telemetry_payload() -> dict[str, Any]:
    """Génère la télémétrie matérielle complète unifiée consommée par /api/settings/system et /api/metrics/dashboard."""
    gpu_name, gpu_percent, gpu_temp_c = get_gpu_info()
    ram_info = get_ram_info()
    storage_info = get_storage_usage()
    power_watts = get_power_watts()
    update_cumulative_energy(power_watts)
    cpu_pct = get_cpu_percent()
    cpu_temp = get_cpu_temp()
    runtime = get_runtime_info()

    mem_total, mem_used, mem_percent = 0, 0, 0.0
    try:
        vm = psutil.virtual_memory()
        mem_total = vm.total
        mem_used = vm.total - vm.available
        mem_percent = vm.percent
    except Exception:
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                lines = f.readlines()
            m = {}
            for l in lines:
                if ":" in l:
                    k, v = l.split(":", 1)
                    m[k.strip()] = int(v.strip().split()[0]) * 1024
            mem_total = m.get("MemTotal", 0)
            avail = m.get("MemAvailable", m.get("MemFree", 0))
            mem_used = max(0, mem_total - avail)
            mem_percent = round((mem_used / mem_total) * 100, 1) if mem_total else 0.0
        except Exception as exc:
            logger.debug("get_system_telemetry_payload : %s", exc)

    return {
        "cpu_name": get_cpu_model_name(),
        "cpu_percent": cpu_pct,
        "cpu_temp_c": cpu_temp,
        "gpu_name": gpu_name,
        "gpu_percent": gpu_percent,
        "gpu_temp_c": gpu_temp_c,
        "power_watts": power_watts,
        "storage_model": get_storage_model(),
        "storage_used_percent": storage_info["used_percent"],
        "storage_free_bytes": storage_info["free_bytes"],
        "storage_total_bytes": storage_info["total_bytes"],
        "storage": storage_info,
        "memory_total_bytes": mem_total,
        "memory_used_bytes": mem_used,
        "memory_percent": mem_percent,
        "ram_brand": ram_info.get("brand"),
        "ram_type": ram_info.get("type"),
        "ram_freq": ram_info.get("freq"),
        "ram_model": ram_info.get("model_label"),
        "runtime": runtime,
    }


def record_hardware_snapshot(db, extra: dict[str, Any] | None = None) -> None:
    """Enregistre un instantané matériel dans la table system_metrics_history."""
    try:
        telemetry = get_system_telemetry_payload()
        import json

        from app.models import SystemMetricsHistory
        extra_json = json.dumps(extra) if extra else None
        snapshot = SystemMetricsHistory(
            cpu_percent=telemetry.get("cpu_percent"),
            cpu_temp_c=telemetry.get("cpu_temp_c"),
            gpu_percent=telemetry.get("gpu_percent"),
            gpu_temp_c=telemetry.get("gpu_temp_c"),
            memory_percent=telemetry.get("memory_percent"),
            memory_used_bytes=telemetry.get("memory_used_bytes"),
            storage_used_percent=telemetry.get("storage_used_percent"),
            storage_free_bytes=telemetry.get("storage_free_bytes"),
            power_watts=telemetry.get("power_watts"),
            extra_data=extra_json,
        )
        db.add(snapshot)
        db.commit()
    except Exception as e:
        logger.debug(f"Échec enregistrement télémétrie snapshot: {e}")
        try:
            db.rollback()
        except Exception as exc:
            logger.debug("record_hardware_snapshot : %s", exc)


def purge_expired_logs_and_metrics(db, retention_days: int = 7) -> dict[str, int]:
    """Supprime les logs d'activité et métriques système plus anciens que retention_days."""
    from app.models import ActivityLog, SystemMetricsHistory
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, retention_days))
    purged_logs = 0
    purged_metrics = 0
    try:
        purged_logs = db.query(ActivityLog).filter(ActivityLog.timestamp < cutoff).delete()
        purged_metrics = db.query(SystemMetricsHistory).filter(SystemMetricsHistory.timestamp < cutoff).delete()
        db.commit()
        if purged_logs > 0 or purged_metrics > 0:
            logger.info(f"Purge automatique réussie ({retention_days}j) : {purged_logs} logs et {purged_metrics} métriques supprimés.")
    except Exception as e:
        logger.error(f"Erreur purge logs/métriques: {e}")
        try:
            db.rollback()
        except Exception as exc:
            logger.debug("purge_expired_logs_and_metrics : %s", exc)
    return {"purged_logs": purged_logs, "purged_metrics": purged_metrics}
