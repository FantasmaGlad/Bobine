"""Historique d'une métrique matérielle : points échantillonnés et statistiques."""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.hardware.telemetry import get_system_telemetry_payload
from app.models import SystemMetricsHistory

_WINDOWS = {"1h": timedelta(hours=1), "6h": timedelta(hours=6), "24h": timedelta(hours=24), "30d": timedelta(days=30)}
_META = {
    "cpu": ("%", "Charge CPU", "cpu_percent"),
    "cpu_temp": ("°C", "Température CPU", "cpu_temp_c"),
    "gpu": ("%", "Charge GPU", "gpu_percent"),
    "gpu_temp": ("°C", "Température GPU", "gpu_temp_c"),
    "memory": ("%", "Utilisation RAM", "memory_percent"),
    "storage": ("%", "Occupation Stockage", "storage_used_percent"),
    "power": ("W", "Puissance consommée", "power_watts"),
}
_MAX_POINTS = 80
_SAMPLED_POINTS = 60


def _start(period: str, now: datetime) -> datetime | None:
    if period == "all":
        return None
    if period == "this_month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return now - _WINDOWS.get(period, timedelta(days=7))


def _describe(metric: str) -> tuple[str, str]:
    if metric in _META:
        return _META[metric][0], _META[metric][1]
    lower = metric.lower()
    unit = "%" if "pct" in lower or "percent" in lower else "°C" if "temp" in lower else "W" if "watt" in lower else ""
    return unit, metric.replace("_", " ").title()


def _sample(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(points) <= _MAX_POINTS:
        return points
    sampled = points[::max(1, len(points) // _SAMPLED_POINTS)]
    if points[-1] not in sampled:
        sampled.append(points[-1])
    return sampled


def hardware_history(db: Session, metric: str, period: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start = _start(period, now)
    query = db.query(SystemMetricsHistory)
    if start is not None:
        query = query.filter(SystemMetricsHistory.timestamp >= start)
    points = [{"timestamp": r.timestamp.isoformat(), "value": round(float(value), 1)}
              for r in query.order_by(SystemMetricsHistory.timestamp.asc()).all()
              if r.timestamp and (value := r.get_metric(metric)) is not None]
    live = get_system_telemetry_payload()
    live_value = live.get(_META[metric][2]) if metric in _META else None
    live_value = live_value or live.get(metric)
    if not points:
        points.append({"timestamp": now.isoformat(), "value": round(float(live_value), 1) if live_value is not None else 0.0})
    values = [p["value"] for p in points]
    unit, label = _describe(metric)
    return {
        "metric": metric,
        "label": label,
        "unit": unit,
        "period": period,
        "points": _sample(points),
        "current": round(float(live_value), 1) if live_value is not None else points[-1]["value"],
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 1),
        "count": len(points),
    }
