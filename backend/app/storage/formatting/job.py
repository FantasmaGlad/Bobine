"""Tâche de formatage : étapes, état public, contrôles et annulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from .model import FormatSpec


STEPS = ("unmount", "recheck", "table", "format", "settle", "readback", "mount_ro", "write_test", "back_ro", "health")


JOB_KEEP_SECONDS = 600.0


@dataclass
class FormatJob:
    id: str
    key: str
    fs: str
    label: str
    disk_name: str
    started_at: float
    steps: dict[str, str] = field(default_factory=lambda: {s: "pending" for s in STEPS})
    stage: str = "starting"
    state: str = "running"
    outcome: str | None = None
    point_of_no_return: bool = False
    cancel_requested: bool = False
    error: dict[str, str] | None = None
    report: dict[str, Any] | None = None
    finished_at: float | None = None
    volume_keys: tuple[str, ...] = ()

    @property
    def can_cancel(self) -> bool:
        return self.state == "running" and not self.point_of_no_return

    def percent(self) -> int:
        done = sum(1 for v in self.steps.values() if v in ("ok", "warn", "skipped"))
        return int(100 * done / len(STEPS))

    def public(self) -> dict[str, Any]:
        return {
            "job_id": self.id, "state": self.state, "stage": self.stage, "outcome": self.outcome, "percent": self.percent(),
            "steps": [{"id": s, "state": self.steps[s]} for s in STEPS], "can_cancel": self.can_cancel,
            "point_of_no_return": self.point_of_no_return, "error": self.error, "report": self.report,
            "fs": self.fs, "label": self.label,
        }


class _Cancelled(Exception):
    pass


class _Checks:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(self, cid: str, ok: bool, **detail: Any) -> None:
        self.items.append({"id": cid, "ok": ok, **detail})

    def all_ok(self) -> bool:
        return all(c["ok"] for c in self.items)

    def last_ok(self) -> bool:
        return bool(self.items) and self.items[-1]["ok"]


def _wanted_label(spec: FormatSpec) -> str:
    return spec.label.upper() if spec.fs == "vfat" else spec.label
