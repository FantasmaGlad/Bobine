"""Ordre de lecture du moteur radio : aléatoire, répétition, file d'attente."""

from __future__ import annotations

import random

from .constants import REPEAT_MODES


class OrderMixin:
    async def set_shuffle(self, on: bool, client_ts: float | None = None):
        self.state["shuffle"] = bool(on)
        order = self.state["order"]
        idx = self.state["index"]
        if on and order and idx is not None and idx + 1 < len(order):
            upcoming = order[idx + 1:]
            random.shuffle(upcoming)
            self.state["order"] = order[: idx + 1] + upcoming
        await self._emit("radio_set_shuffle", client_ts)

    async def set_repeat(self, mode: str, client_ts: float | None = None):
        if mode not in REPEAT_MODES:
            return
        self.state["repeat"] = mode
        await self._emit("radio_set_repeat", client_ts)

    async def add_to_queue(self, track: dict, client_ts: float | None = None):
        """Ajoute une piste en FIN de file d'attente."""
        order = self.state["order"]
        order.append(track)
        self.state["order"] = order
        if self.state["index"] is None:
            self.state["index"] = len(order) - 1
            self._sync_current()
        await self._emit("radio_queue_changed", client_ts)

    async def play_next(self, track: dict, client_ts: float | None = None):
        """« Lire ensuite » : insère une piste juste après la piste courante, devant tout ce qui est déjà en file d'attente."""
        order = self.state["order"]
        idx = self.state["index"]
        insert_at = (idx + 1) if idx is not None else len(order)
        order.insert(insert_at, track)
        self.state["order"] = order
        if self.state["index"] is None:
            self.state["index"] = insert_at
            self._sync_current()
        await self._emit("radio_queue_changed", client_ts)

    async def move_in_order(self, from_index: int, to_index: int, client_ts: float | None = None):
        """Déplace une piste de la file « À suivre » (glisser-déposer de l'admin)."""
        order = self.state["order"]
        cur = self.state["index"]
        if cur is None or not order:
            return
        first = cur + 1
        if not (first <= from_index < len(order)):
            return
        target = max(first, min(to_index, len(order) - 1))
        if target == from_index:
            return
        order.insert(target, order.pop(from_index))
        self.state["order"] = order
        await self._emit("radio_queue_changed", client_ts)

    async def remove_from_order(self, index: int, client_ts: float | None = None):
        """Retire une piste de l'ordre de lecture (file d'attente)."""
        order = self.state["order"]
        if not (0 <= index < len(order)):
            return
        cur = self.state["index"] or 0
        order.pop(index)
        if index < cur:
            self.state["index"] = cur - 1
        elif index == cur:
            self.state["index"] = min(cur, len(order) - 1) if order else None
        self.state["order"] = order
        if not order:
            self.state.update({"playing": False, "state": "idle"})
            self._clock.reset()
        self._sync_current()
        if index == cur and order:
            self.state["position_seconds"] = 0.0
            if self.state["playing"]:
                self._start_clock(0.0)
            else:
                self._clock.reset()
        await self._emit("radio_queue_changed", client_ts)

